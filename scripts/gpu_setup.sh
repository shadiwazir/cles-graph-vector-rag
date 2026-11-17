#!/usr/bin/env bash
# Prepare a rented GPU machine for `train_sft` (docs/06). Two modes:
#
#   scripts/gpu_setup.sh push  user@host port    run on the LAPTOP: rsync repo + newest dataset
#   scripts/gpu_setup.sh setup                    run on the GPU MACHINE: environment + dry run
#   scripts/gpu_setup.sh run <name> <config>      run on the GPU MACHINE: train_sft in the background
#   scripts/gpu_setup.sh eval <system>            run on the GPU MACHINE: eval_generate with one
#                                                 system of eval/systems.yaml (run name eval-<system>)
#   scripts/gpu_setup.sh serve [adapter_dir]      run on the GPU MACHINE: install vLLM (own venv) and serve
#                                                 the base model plus the adapter as model "cles"
#   scripts/gpu_setup.sh serve-wait               run on the GPU MACHINE: block until "cles" answers
#   scripts/gpu_setup.sh wait <name>              run on the GPU MACHINE: block until the run ends
#   scripts/gpu_setup.sh push-folds user@host port <folds-dir-name>   run on the LAPTOP: rsync repo +
#                                                 the dev folds (never the locked test fold)
#   scripts/gpu_setup.sh folds <folds-dir-name> <fold>...   run on the GPU MACHINE: train an adapter
#                                                 per fold and generate its answers (gpu_folds.sh)
#   scripts/gpu_setup.sh pull-folds user@host port <folds-dir-name>   run on the LAPTOP: fetch the
#                                                 generated answers and the MLflow file
#
# `run` writes /workspace/runs/<name>.log and, when the process ends, /workspace/runs/<name>.exit
# (the exit code). Wait on that file, never on `pgrep -f` over ssh: the ssh command line matches
# its own pattern and the wait never ends while the pod keeps billing.
#
# Everything lives under /workspace (the persistent volume) so a stopped pod keeps it.
# The machine needs no API keys. Never copy .env to it.
set -euo pipefail

MODE="${1:-}"
REMOTE_DIR="${REMOTE_DIR:-/workspace/cles}"

case "$MODE" in
  push)
    HOST="${2:?usage: gpu_setup.sh push user@host port}"
    PORT="${3:?usage: gpu_setup.sh push user@host port}"
    cd "$(dirname "$0")/.."
    DATASET="$(ls -1dt artifacts/datasets/*/ | head -1)"; DATASET="${DATASET%/}"   # newest by time, no trailing slash
    SSH="ssh -p $PORT -i ${SSH_KEY:-$HOME/.ssh/id_ed25519}"
    echo "dataset: $DATASET"
    rsync -rltz --no-owner --no-group -e "$SSH" \
      --exclude .venv --exclude .env --exclude data --exclude mlruns --exclude artifacts \
      --exclude .dvc/cache --exclude .dvc/tmp --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache --exclude .git \
      ./ "$HOST:$REMOTE_DIR/"
    $SSH "$HOST" "mkdir -p $REMOTE_DIR/artifacts/datasets"
    rsync -rltz --no-owner --no-group -e "$SSH" "$DATASET" "$HOST:$REMOTE_DIR/artifacts/datasets/"
    rsync -rltz --no-owner --no-group -e "$SSH" artifacts/datasets.dvc "$HOST:$REMOTE_DIR/artifacts/"
    rsync -rltz --no-owner --no-group -e "$SSH" data.dvc "$HOST:$REMOTE_DIR/"
    echo "pushed. Next: ssh in, then: cd $REMOTE_DIR && scripts/gpu_setup.sh setup"
    ;;
  push-folds)
    HOST="${2:?usage: gpu_setup.sh push-folds user@host port <folds-dir-name>}"
    PORT="${3:?usage: gpu_setup.sh push-folds user@host port <folds-dir-name>}"
    FOLDS="${4:?usage: gpu_setup.sh push-folds user@host port <folds-dir-name>}"
    cd "$(dirname "$0")/.."
    [[ -d "artifacts/folds/$FOLDS" ]] || { echo "no artifacts/folds/$FOLDS" >&2; exit 2; }
    SSH="ssh -p $PORT -i ${SSH_KEY:-$HOME/.ssh/id_ed25519}"
    rsync -rltz --no-owner --no-group -e "$SSH" \
      --exclude .venv --exclude .env --exclude data --exclude mlruns --exclude artifacts \
      --exclude .dvc/cache --exclude .dvc/tmp --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache --exclude .git \
      ./ "$HOST:$REMOTE_DIR/"
    $SSH "$HOST" "mkdir -p $REMOTE_DIR/artifacts/folds/$FOLDS"
    # the test fold is locked: it is not even copied to the machine
    rsync -rltz --no-owner --no-group -e "$SSH" --exclude test --exclude eval \
      "artifacts/folds/$FOLDS/" "$HOST:$REMOTE_DIR/artifacts/folds/$FOLDS/"
    echo "pushed code and the dev folds of $FOLDS. Next, on the machine: scripts/gpu_setup.sh folds $FOLDS dev1 dev2 dev3"
    ;;
  folds)
    FOLDS="${2:?usage: gpu_setup.sh folds <folds-dir-name> <fold>...}"
    shift 2
    [[ $# -gt 0 ]] || { echo "usage: gpu_setup.sh folds <folds-dir-name> <fold>..." >&2; exit 2; }
    mkdir -p /workspace/runs
    rm -f /workspace/runs/folds.exit
    cd "$REMOTE_DIR"
    setsid nohup bash scripts/gpu_folds.sh "$FOLDS" "$@" < /dev/null > /workspace/runs/folds.log 2>&1 &
    echo "started folds $* (log /workspace/runs/folds.log, marker /workspace/runs/folds.exit)"
    ;;
  pull-folds)
    HOST="${2:?usage: gpu_setup.sh pull-folds user@host port <folds-dir-name>}"
    PORT="${3:?usage: gpu_setup.sh pull-folds user@host port <folds-dir-name>}"
    FOLDS="${4:?usage: gpu_setup.sh pull-folds user@host port <folds-dir-name>}"
    cd "$(dirname "$0")/.."
    SSH="ssh -p $PORT -i ${SSH_KEY:-$HOME/.ssh/id_ed25519}"
    RSYNC=(rsync -rltz --no-owner --no-group -e "$SSH")
    BAD=0
    # A CPU-only image may have no rsync on the machine: then the files come over ssh with tar/cat.
    HAS_RSYNC=$($SSH "$HOST" "command -v rsync >/dev/null && echo yes || echo no" 2>/dev/null || echo no)
    pull_dir() {  # a folder, same relative path here as on the machine
      mkdir -p "$1"
      if [[ "$HAS_RSYNC" == "yes" ]]; then
        "${RSYNC[@]}" "$HOST:$REMOTE_DIR/$1/" "$1/"
      else
        $SSH "$HOST" "tar -C '$REMOTE_DIR/$1' -cf - ." | tar -C "$1" -xf -
      fi
    }
    pull_file() {  # a file to a path here
      if [[ "$HAS_RSYNC" == "yes" ]]; then
        "${RSYNC[@]}" "$HOST:$REMOTE_DIR/$1" "$2"
      else
        $SSH "$HOST" "cat '$REMOTE_DIR/$1'" > "$2"
      fi
    }
    # Everything the run produced only on the machine comes home before the pod may be stopped:
    # the answers of each fold, its adapter, and the MLflow file. Every item is verified.
    for fold in dev1 dev2 dev3; do
      answers="artifacts/folds/$FOLDS/$fold/eval/finetuned"
      pull_dir "$answers" || { echo "FAILED: answers of $fold" >&2; BAD=1; }
      have=$(wc -l < "$answers/outputs.jsonl" 2>/dev/null || echo 0)
      want=$(wc -l < "artifacts/folds/$FOLDS/$fold/eval.jsonl" 2>/dev/null || echo -1)
      [[ "$have" == "$want" ]] || { echo "FAILED: $fold has $have of $want answers" >&2; BAD=1; }

      adapter="$($SSH "$HOST" "cat /workspace/runs/adapter-$fold.txt 2>/dev/null" || true)"
      if [[ -z "$adapter" ]]; then
        echo "FAILED: no adapter path recorded on the machine for $fold" >&2; BAD=1; continue
      fi
      pull_dir "$adapter" || { echo "FAILED: adapter of $fold" >&2; BAD=1; }
      remote_size=$($SSH "$HOST" "stat -c %s $REMOTE_DIR/$adapter/adapter_model.safetensors" 2>/dev/null || echo -1)
      local_size=$(stat -c %s "$adapter/adapter_model.safetensors" 2>/dev/null || echo -2)
      [[ "$remote_size" == "$local_size" ]] || { echo "FAILED: adapter of $fold differs ($local_size bytes here, $remote_size there)" >&2; BAD=1; }
      echo "$fold: $have answers, adapter $adapter ($local_size bytes)"
    done
    pull_file "artifacts/mlflow.db" artifacts/mlflow-gpu-folds.db \
      || { echo "FAILED: the MLflow file" >&2; BAD=1; }
    if [[ "$BAD" == "0" ]]; then
      echo "ALL PULLED AND VERIFIED: the pod can be stopped. Left on the pod on purpose: model caches, environments, checkpoints."
      echo "Next: dvc add artifacts/runs artifacts/folds && dvc push; MLflow runs: python -m cles.mlflow_import --source sqlite:///artifacts/mlflow-gpu-folds.db (without --register)"
    else
      echo "NOT COMPLETE: do not stop the pod yet." >&2
      exit 1
    fi
    ;;
  setup)
    cd "$REMOTE_DIR"
    # Non-interactive ssh commands do not read .bashrc, so every command sources /workspace/env.sh.
    echo 'export HF_HOME=/workspace/.cache/huggingface UV_CACHE_DIR=/workspace/.cache/uv UV_LINK_MODE=copy' > /workspace/env.sh
    # shellcheck disable=SC1091
    . /workspace/env.sh
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    # The venv reuses the image's CUDA build of torch (no second torch download).
    [[ -d /workspace/venv ]] || uv venv --system-site-packages --python python3 /workspace/venv
    # shellcheck disable=SC1091
    . /workspace/venv/bin/activate
    # Unsloth goes in a second step: with the newer pins in one command, uv falls back to unsloth 2024.8.
    # The current Unsloth steps trl, datasets and torch down a little; that is expected.
    uv pip install -e . "accelerate>=1.15.0" "mlflow>=3.18.0" "peft>=0.21.2" "trl>=1.15.0" "datasets>=4.8"
    uv pip install "unsloth>=2026.1"
    python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
    cat > .env <<ENV
DOMAIN_PACK=legal_ca_on
MLFLOW_TRACKING_URI=sqlite:///artifacts/mlflow.db
SFT_CONFIG=configs/sft/qwen3_8b_poc.yaml
ENV
    cles run train_sft --dry-run
    echo "setup done. Activate with: . /workspace/venv/bin/activate && cd $REMOTE_DIR"
    ;;
  run)
    NAME="${2:?usage: gpu_setup.sh run <name> <config>}"
    CONFIG="${3:?usage: gpu_setup.sh run <name> <config>}"
    mkdir -p /workspace/runs
    rm -f "/workspace/runs/$NAME.exit"
    cd "$REMOTE_DIR"
    setsid nohup bash -c ". /workspace/env.sh && . /workspace/venv/bin/activate \
      && SFT_CONFIG='$CONFIG' cles run train_sft > /workspace/runs/$NAME.log 2>&1; \
      echo \$? > /workspace/runs/$NAME.exit" < /dev/null > /dev/null 2>&1 &
    echo "started $NAME (log /workspace/runs/$NAME.log, done marker /workspace/runs/$NAME.exit)"
    ;;
  eval)
    SYSTEM="${2:?usage: gpu_setup.sh eval <system>}"
    mkdir -p /workspace/runs
    rm -f "/workspace/runs/eval-$SYSTEM.exit"
    cd "$REMOTE_DIR"
    setsid nohup bash -c ". /workspace/env.sh && . /workspace/venv/bin/activate \\
      && EVAL_SYSTEM='$SYSTEM' cles run eval_generate > /workspace/runs/eval-$SYSTEM.log 2>&1; \\
      echo \\$? > /workspace/runs/eval-$SYSTEM.exit" < /dev/null > /dev/null 2>&1 &
    echo "started eval-$SYSTEM (log /workspace/runs/eval-$SYSTEM.log, marker eval-$SYSTEM.exit)"
    ;;
  serve)
    ADAPTER="${2:-artifacts/runs/3a752888/adapter}"
    mkdir -p /workspace/runs
    rm -f /workspace/runs/serve.exit
    # vLLM pins its own torch, so it gets its own venv next to the training one. Everything runs in
    # the background (the install takes minutes); the server listens on the pod's localhost only,
    # reach it through an SSH tunnel.
    setsid nohup bash -c ". /workspace/env.sh \\
      && { [ -d /workspace/venv-vllm ] || uv venv --python python3 /workspace/venv-vllm; } \\
      && . /workspace/venv-vllm/bin/activate \\
      && { python -c 'import vllm' 2>/dev/null || uv pip install 'vllm==0.33.0'; } \\
      && vllm serve Qwen/Qwen3-8B --enable-lora --lora-modules cles=$REMOTE_DIR/$ADAPTER \\
           --max-lora-rank 64 --max-model-len 12288 --dtype bfloat16 \\
           --gpu-memory-utilization 0.90 --host 127.0.0.1 --port 8000 \\
      ; echo \\$? > /workspace/runs/serve.exit" < /dev/null > /workspace/runs/serve.log 2>&1 &
    echo "started serve (log /workspace/runs/serve.log, marker /workspace/runs/serve.exit)"
    ;;
  serve-wait)
    until curl -sf http://127.0.0.1:8000/v1/models 2>/dev/null | grep -q '"cles"'; do
      if [[ -f /workspace/runs/serve.exit ]]; then
        echo "server exited with code $(cat /workspace/runs/serve.exit); see /workspace/runs/serve.log" >&2
        exit 1
      fi
      sleep 10
    done
    echo "model cles is served on the pod at http://127.0.0.1:8000/v1"
    ;;
  wait)
    NAME="${2:?usage: gpu_setup.sh wait <name>}"
    until [[ -f "/workspace/runs/$NAME.exit" ]]; do sleep 10; done
    echo "run $NAME exit code: $(cat "/workspace/runs/$NAME.exit")"
    ;;
  *)
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
