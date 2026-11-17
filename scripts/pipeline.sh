#!/usr/bin/env bash
# CLES pipeline driver: one entry point for every step, so a scheduler or CI job can call it.
#
#   scripts/pipeline.sh <step> [--limit N]
#
# Steps (run in this order by `all`):
#   preflight   check tools, .env, PDFs, pack; run the unit tests
#   infra       start the whole stack: Postgres, Neo4j (Flyway migrates the schema), MLflow,
#               OpenTelemetry Collector, Phoenix, Prometheus, Grafana; wait until healthy
#   data        ingest embed build_indexes extract graph_load record_manifest   (extract is PAID)
#   dataset     build_dataset check_dataset                                       (build_dataset is PAID)
#   folds       build_folds, check_dataset on every fold, folds_report (ADR 0023): rolling-origin dev
#               folds and a locked test fold. No paid call unless FOLDS_TARGETS=generate (PAID,
#               gated); the test fold is evaluated only with FOLDS_INCLUDE_TEST=1 and a reason
#   folds-targets  PAID: generate the missing training targets for all folds (ceiling MAX_COST_USD,
#               enforced inside the stage too), then check every fold and report
#   folds-eval  PAID: OpenAI baseline on the dev folds (FOLDS_EVAL_SYSTEMS, default openai), scored
#               per fold with the replayed calibrations, then pooled by folds_report
#   train       train_sft   (needs a GPU; on a laptop use `train-dry`)
#   train-dry   train_sft --dry-run: leakage re-check, token statistics, template preview
#   eval        eval_generate with the OpenAI baseline (PAID), then eval_score
#   eval-score  eval_score only: score every system in artifacts/eval/*/outputs.jsonl
#   judge       judge_eval (PAID, public decisions only), eval_score, judge_calibrate
#   accept      accept_check: acceptance criteria (eval/acceptance.yaml) for the model version,
#               provisional (exit 6 when a blocking criterion fails)
#   drift       drift_check: latest evaluation vs eval/baseline.json, live traffic vs reference
#               (exit 5 when there are violations)
#   snapshot    dvc add + dvc push of the exports, datasets, evaluation outputs and adapters
#   alerts-test unit tests of the Prometheus alert rules (promtool in Docker)
#   mlflow-import --source sqlite:///file.db   copy runs of a GPU machine's MLflow file into the server
#   console     the web console on http://localhost:${CONSOLE_PORT:-8000}: ask the advisor, results
#               explorer, platform tools (MLflow, Grafana, Phoenix, Prometheus), about
#   explore     results explorer on http://localhost:${EXPLORER_PORT:-8001} (reads files only)
#   all         preflight infra data dataset train-dry
#   status      row counts and the latest run summaries
#   reset       DESTROY the Postgres and Neo4j volumes (needs CONFIRM_RESET=1)
#
# Paid steps first run the stage with --dry-run and print the estimate. They only go on when
# CONFIRM_PAID=1 is set and the estimate is at most MAX_COST_USD. Exit codes: 0 ok, 1 stage
# failed, 2 bad usage or missing input, 3 paid step not confirmed, 4 estimate above the ceiling.
#
# Environment (all optional; .env is read first):
#   PIPELINE_DATA_DIR  folder with the PDFs (overrides DATA_DIR in .env)   (default data/criminal_and_civil)
#   CONFIRM_PAID   1 to allow paid LLM calls                 (default unset)
#   MAX_COST_USD   ceiling for one paid step's estimate      (default 10)
#   LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK     (defaults 0.75 / 4.50, unverified)
#   PIPELINE_LOG_DIR  where logs go                          (default artifacts/pipeline)
#   SKIP_TESTS     1 to skip pytest in preflight
set -euo pipefail

cd "$(dirname "$0")/.."

# Variables given on the command line win over .env (for example LLM_BASE_URL or
# ALLOW_EXTERNAL_GENERATOR for one run): remember them, load .env, then put them back.
declare -A CALLER_ENV
if [[ -f .env ]]; then
  while read -r key; do
    [[ -n "${!key+x}" ]] && CALLER_ENV[$key]="${!key}"
  done < <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env || true)
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
  for key in "${!CALLER_ENV[@]}"; do export "$key=${CALLER_ENV[$key]}"; done
fi

# MLflow, DVC and telemetry are part of every step: telemetry is switched on whenever the
# collector answers, MLflow tracking is best effort inside every stage (cles.tracking).
if curl -s -o /dev/null --max-time 1 "${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:4318}"; then
  export TELEMETRY_ENABLED=true
fi

export DATA_DIR="${PIPELINE_DATA_DIR:-data/criminal_and_civil}"
export LLM_PRICE_INPUT_PER_MTOK="${LLM_PRICE_INPUT_PER_MTOK:-0.75}"
export LLM_PRICE_OUTPUT_PER_MTOK="${LLM_PRICE_OUTPUT_PER_MTOK:-4.50}"
MAX_COST_USD="${MAX_COST_USD:-10}"
COMPOSE=(docker compose --env-file .env -f infra/docker-compose.yml)

LOG_ROOT="${PIPELINE_LOG_DIR:-artifacts/pipeline}"
RUN_TAG="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$LOG_ROOT/$RUN_TAG"

STEP="${1:-}"
[[ $# -gt 0 ]] && shift
LIMIT_ARGS=()
SOURCE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT_ARGS=(--limit "$2"); shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '[pipeline %s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die() { say "ERROR: $*"; exit "${2:-1}"; }

# Run stages through the thin runner; keep each JSON summary line in the log folder.
run_stages() {
  mkdir -p "$LOG_DIR"
  for stage in "$@"; do
    say "stage $stage"
    local out="$LOG_DIR/$stage.log"
    if ! uv run cles run "$stage" "${LIMIT_ARGS[@]}" 2>"$out.err" | tee "$out" >>"$LOG_DIR/summary.jsonl"; then
      tail -5 "$out.err" >&2
      die "stage $stage failed (see $out and $out.err)"
    fi
    tail -1 "$out" | cut -c1-400 >&2
  done
}

# Paid gate: estimate with --dry-run, compare with the ceiling, require explicit confirmation.
paid_gate() {
  local stage="$1" est
  est="$(uv run cles run "$stage" --dry-run "${LIMIT_ARGS[@]}" 2>/dev/null | tail -1 \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("est_cost_usd"))')"
  say "$stage estimate: ${est} USD (ceiling $MAX_COST_USD; prices unverified, real cost can be higher)"
  [[ "$est" == "None" ]] && die "no estimate: set LLM_PRICE_INPUT_PER_MTOK and LLM_PRICE_OUTPUT_PER_MTOK" 2
  python3 -c "import sys; sys.exit(0 if float('$est') <= float('$MAX_COST_USD') else 1)" \
    || die "estimate above MAX_COST_USD" 4
  [[ "${CONFIRM_PAID:-}" == "1" ]] || die "paid step not confirmed: rerun with CONFIRM_PAID=1" 3
}

step_preflight() {
  command -v uv >/dev/null || die "uv not found" 2
  command -v docker >/dev/null || die "docker not found" 2
  [[ -f .env ]] || die ".env missing: cp .env.example .env and fill it in" 2
  for var in POSTGRES_PASSWORD NEO4J_PASSWORD LLM_MODEL OPENAI_API_KEY; do
    [[ -n "${!var:-}" ]] || die "$var is empty in .env" 2
  done
  local pdfs
  pdfs="$(find "$DATA_DIR" -maxdepth 1 -name '*.pdf' 2>/dev/null | wc -l)"
  [[ "$pdfs" -gt 0 ]] || die "no PDFs in $DATA_DIR" 2
  say "$pdfs PDFs in $DATA_DIR"
  uv sync --extra embed --quiet
  if [[ "${SKIP_TESTS:-}" != "1" ]]; then uv run pytest -q >&2 || die "tests failed"; fi
  run_stages validate_pack
}

step_infra() {
  "${COMPOSE[@]}" --profile observability --profile training up -d >&2
  for _ in $(seq 1 30); do
    local bad
    bad="$("${COMPOSE[@]}" ps --format '{{.Name}} {{.Health}}' postgres neo4j | grep -vc healthy || true)"
    if [[ "$bad" == "0" ]] \
      && curl -sf -o /dev/null http://localhost:5000/health \
      && curl -s -o /dev/null http://127.0.0.1:6006/ \
      && curl -sf -o /dev/null http://localhost:9090/-/ready; then
      say "stack healthy: postgres, neo4j, mlflow :5000, phoenix :6006, prometheus :9090, grafana :3000"
      export TELEMETRY_ENABLED=true
      return
    fi
    sleep 5
  done
  die "services did not become healthy"
}

# Version data with DVC after the step that produced it, so the next step records the new hash.
# Best effort: DVC trouble is reported, it does not stop the pipeline.
snapshot() {
  say "dvc snapshot: $*"
  uv run dvc add "$@" >&2 && uv run dvc push >&2 \
    || say "WARNING: dvc snapshot failed for $* (run scripts/pipeline.sh snapshot to retry)"
  say "commit the changed .dvc files with git to pin these versions"
}

step_snapshot() {
  local paths=()
  for p in artifacts/exports artifacts/datasets artifacts/eval artifacts/runs data; do
    [[ -e "$p" ]] && paths+=("$p")
  done
  snapshot "${paths[@]}"
}

step_data() {
  run_stages ingest embed build_indexes
  paid_gate extract
  run_stages extract export_extractions
  snapshot artifacts/exports
  run_stages graph_load record_manifest
}

step_dataset() {
  paid_gate build_dataset
  run_stages build_dataset check_dataset
  snapshot artifacts/datasets
}

# Rolling-origin folds (ADR 0023). Default: no paid call, only cached targets are used. With
# FOLDS_TARGETS=generate the missing training targets are paid for, behind the paid gate. The test
# fold stays locked unless FOLDS_INCLUDE_TEST=1 and FOLDS_TEST_REASON are given (it is logged).
step_folds() {
  [[ "${FOLDS_TARGETS:-cached}" == "generate" ]] && paid_gate build_folds
  run_stages build_folds
  local root fold
  root="$(ls -1dt artifacts/folds/*/ | head -1)"
  for fold in "$root"*/; do
    [[ -f "$fold/manifest.json" ]] && DATASET_DIR="$fold" run_stages check_dataset
  done
  FOLDS_DIR="$root" run_stages folds_report
  snapshot artifacts/folds
}

# Baseline answers from the configured LLM on the held-out examples. The examples are public
# decisions, so the external-generator guard is lifted for this step only.
step_eval() {
  EVAL_SYSTEM=openai paid_gate eval_generate
  EVAL_SYSTEM=openai ALLOW_EXTERNAL_GENERATOR=true run_stages eval_generate
  step_eval_score
}

# Generate the missing training targets of all folds (PAID, cached). The stage refuses to start when
# its estimate is above the ceiling and stops starting calls when the spend passes it.
step_folds_targets() {
  [[ "${CONFIRM_PAID:-}" == "1" ]] || die "paid step not confirmed: rerun with CONFIRM_PAID=1" 3
  FOLDS_TARGETS=generate FOLDS_MAX_COST_USD="$MAX_COST_USD" run_stages build_folds
  local root fold
  root="$(ls -1dt artifacts/folds/*/ | head -1)"
  for fold in "$root"*/; do
    [[ -f "$fold/manifest.json" ]] && DATASET_DIR="$fold" run_stages check_dataset
  done
  FOLDS_DIR="$root" run_stages folds_report
  snapshot artifacts/folds
}

# Systems (EVAL_SYSTEM names from eval/systems.yaml) generated and scored on every dev fold. Model
# outputs live in <fold>/eval/<system>/; the test fold is never evaluated here.
step_folds_eval() {
  local root fold systems system
  root="$(ls -1dt artifacts/folds/*/ | head -1)"
  systems="${FOLDS_EVAL_SYSTEMS:-openai}"
  for fold in "$root"dev*/; do
    for system in $systems; do
      DATASET_DIR="$fold" EVAL_OUT_DIR="$fold/eval" EVAL_SYSTEM="$system" paid_gate eval_generate
    done
  done
  for fold in "$root"dev*/; do
    for system in $systems; do
      DATASET_DIR="$fold" EVAL_OUT_DIR="$fold/eval" EVAL_SYSTEM="$system" \
        ALLOW_EXTERNAL_GENERATOR=true run_stages eval_generate
    done
    DATASET_DIR="$fold" EVAL_OUT_DIR="$fold/eval" EVAL_METRICS_FILE="$fold/eval_metrics.json" \
      run_stages eval_score
  done
  FOLDS_DIR="$root" run_stages folds_report
  snapshot artifacts/folds
}

# Score, then version the outputs and check for regressions (exit 5 on violations).
step_eval_score() {
  run_stages eval_score
  snapshot artifacts/eval
  run_stages accept_check  # informational here: `accept` is the gate
  tail -1 "$LOG_DIR/accept_check.log" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("acceptance (provisional):", d.get("status"), d.get("blocking_failed_ids"))' >&2
  step_drift
}

# LLM-as-judge faithfulness of every evaluated answer, then calibration against your labels.
step_judge() {
  paid_gate judge_eval
  ALLOW_EXTERNAL_GENERATOR=true run_stages judge_eval
  run_stages eval_score judge_calibrate
  snapshot artifacts/eval
}

step_accept() {
  run_stages accept_check
  local status
  status="$(tail -1 "$LOG_DIR/accept_check.log" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status"), d.get("blocking_failed_ids"))')"
  say "acceptance (provisional): $status"
  [[ "$status" == accepted_provisional* ]] || die "model version not accepted: $status" 6
}

step_drift() {
  run_stages drift_check
  local violations
  violations="$(tail -1 "$LOG_DIR/drift_check.log" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("violations", 0))')"
  if [[ "$violations" != "0" ]]; then
    tail -1 "$LOG_DIR/drift_check.log" | python3 -c 'import json,sys; [print("  -", p) for p in json.load(sys.stdin).get("problems", [])]' >&2
    die "drift check found $violations violation(s)" 5
  fi
}

step_alerts_test() {
  docker run --rm --entrypoint promtool -v "$PWD/infra/observability:/w:ro" prom/prometheus:v3.16.0 \
    test rules /w/alerts_test.yml >&2
}

step_mlflow_import() {
  [[ -n "$SOURCE" ]] || die "usage: scripts/pipeline.sh mlflow-import --source sqlite:///artifacts/mlflow-gpu.db" 2
  uv run python -m cles.mlflow_import --source "$SOURCE" --register cles-advisor --register-match poc
}

step_console() {
  say "web console: http://localhost:${CONSOLE_PORT:-8000}/ (Ctrl+C to stop)"
  exec uv run uvicorn cles.console.app:create_app --factory --port "${CONSOLE_PORT:-8000}"
}

step_explore() {
  say "results explorer: http://localhost:${EXPLORER_PORT:-8001}/ (Ctrl+C to stop)"
  exec uv run uvicorn cles.evaluation.explorer:create_app --factory --port "${EXPLORER_PORT:-8001}"
}

step_train() { run_stages train_sft; }

step_train_dry() {
  mkdir -p "$LOG_DIR"
  uv run cles run train_sft --dry-run 2>"$LOG_DIR/train_dry.err" | tee "$LOG_DIR/train_dry.log" >>"$LOG_DIR/summary.jsonl" \
    || die "train dry run failed (see $LOG_DIR/train_dry.err)"
}

step_status() {
  "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "select 'documents' t, count(*) from documents union all select 'chunks', count(*) from chunks
     union all select 'extractions', count(*) from extractions union all select 'training_targets', count(*) from training_targets"
  "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "select stage, started_at, finished_at from ingestion_runs order by started_at desc limit 8" || true
  ls -1d artifacts/datasets/*/ 2>/dev/null | tail -3 || true
}

step_reset() {
  [[ "${CONFIRM_RESET:-}" == "1" ]] || die "reset deletes all Postgres and Neo4j data (extraction cache included): rerun with CONFIRM_RESET=1" 3
  "${COMPOSE[@]}" down -v >&2
}

case "$STEP" in
  preflight) step_preflight ;;
  infra) step_infra ;;
  data) step_data ;;
  dataset) step_dataset ;;
  folds) step_folds ;;
  folds-targets) step_folds_targets ;;
  folds-eval) step_folds_eval ;;
  train) step_train ;;
  train-dry) step_train_dry ;;
  eval) step_eval ;;
  eval-score) step_eval_score ;;
  judge) step_judge ;;
  accept) step_accept ;;
  drift) step_drift ;;
  snapshot) step_snapshot ;;
  alerts-test) step_alerts_test ;;
  mlflow-import) step_mlflow_import ;;
  console) step_console ;;
  explore) step_explore ;;
  all) step_preflight; step_infra; step_data; step_dataset; step_train_dry ;;
  status) step_status ;;
  reset) step_reset ;;
  *) sed -n '2,50p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
say "step $STEP done (logs: $LOG_DIR)"
