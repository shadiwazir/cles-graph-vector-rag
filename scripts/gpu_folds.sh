#!/usr/bin/env bash
# Runs ON the GPU pod (started by `scripts/gpu_setup.sh folds`): for each development fold, train an
# adapter on the fold's training set, then generate answers to the fold's held-out examples with it.
#
#   scripts/gpu_folds.sh <folds-dir-name> <fold> [<fold> ...]
#
# Logs and markers are in /workspace/runs: train-<fold>.log/.err, eval-<fold>.log/.err and
# adapter-<fold>.txt (the adapter path); the whole run writes folds.exit (0 = all folds done).
# It stops at the first failure, so a broken run does not keep the pod billing. Run it again to
# continue: finished adapters are kept and generated answers are cached.
set -uo pipefail

FOLDS="${1:?usage: gpu_folds.sh <folds-dir-name> <fold>...}"
shift
[[ $# -gt 0 ]] || { echo "usage: gpu_folds.sh <folds-dir-name> <fold>..." >&2; exit 2; }

cd /workspace/cles || exit 2
# shellcheck disable=SC1091
. /workspace/env.sh
# shellcheck disable=SC1091
. /workspace/venv/bin/activate
mkdir -p /workspace/runs
rm -f /workspace/runs/folds.exit

fail() {
  echo "FAILED: $*" >&2
  echo 1 > /workspace/runs/folds.exit
  exit 1
}

for fold in "$@"; do
  dir="artifacts/folds/$FOLDS/$fold"
  [[ -f "$dir/eval.jsonl" ]] || fail "no dataset in $dir"
  adapter_file="/workspace/runs/adapter-$fold.txt"
  if [[ ! -s "$adapter_file" ]]; then
    echo "$(date +%H:%M:%S) training $fold"
    # Fold adapters go to their own registry name, not to the product's cles-advisor model.
    DATASET_DIR="$dir" SFT_CONFIG=configs/sft/qwen3_8b_poc.yaml MLFLOW_REGISTERED_MODEL=cles-advisor-folds \
      cles run train_sft > "/workspace/runs/train-$fold.log" 2> "/workspace/runs/train-$fold.err" \
      || fail "training $fold (see /workspace/runs/train-$fold.err)"
    tail -1 "/workspace/runs/train-$fold.log" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["adapter"])' > "$adapter_file" \
      || fail "no adapter path in the training summary of $fold"
  fi
  adapter="$(cat "$adapter_file")"
  echo "$(date +%H:%M:%S) generating answers for $fold with $adapter"
  DATASET_DIR="$dir" EVAL_OUT_DIR="$dir/eval" EVAL_SYSTEM=finetuned EVAL_ADAPTER="$adapter" \
    cles run eval_generate > "/workspace/runs/eval-$fold.log" 2> "/workspace/runs/eval-$fold.err" \
    || fail "answer generation for $fold (see /workspace/runs/eval-$fold.err)"
  echo "$(date +%H:%M:%S) $fold done"
done
echo 0 > /workspace/runs/folds.exit
