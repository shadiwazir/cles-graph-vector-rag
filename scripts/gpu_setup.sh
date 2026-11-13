#!/usr/bin/env bash
# Prepare a rented GPU machine for `train_sft` (docs/06). Two modes:
#
#   scripts/gpu_setup.sh push  user@host port    run on the LAPTOP: rsync repo + newest dataset
#   scripts/gpu_setup.sh setup                    run on the GPU MACHINE: environment + dry run
#   scripts/gpu_setup.sh run <name> <config>      run on the GPU MACHINE: train_sft in the background
#   scripts/gpu_setup.sh wait <name>              run on the GPU MACHINE: block until the run ends
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
  wait)
    NAME="${2:?usage: gpu_setup.sh wait <name>}"
    until [[ -f "/workspace/runs/$NAME.exit" ]]; do sleep 10; done
    echo "run $NAME exit code: $(cat "/workspace/runs/$NAME.exit")"
    ;;
  *)
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
