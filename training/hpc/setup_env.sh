#!/usr/bin/env bash
# One-time HiPerGator setup: Python env + a Jupyter kernel named "PHA training".
#
# Only the repo's training/ folder is needed on HiPerGator, e.g. /blue/<group>/<gatorlink>/pha/training
#
#   bash /blue/<group>/<gatorlink>/pha/training/hpc/setup_env.sh [BASE]
#
# BASE defaults to the folder containing training/ (here: .../pha). Everything large (venv with
# CUDA torch, Hugging Face cache, llama.cpp build, training runs) goes under BASE on /blue,
# not your home directory (small quota).
set -euo pipefail

TRAINING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$(mkdir -p "${1:-$TRAINING_DIR/..}" && cd "${1:-$TRAINING_DIR/..}" && pwd)"
ENV="$BASE/venv"
mkdir -p "$BASE"/{hf-cache,runs,uv-cache}
export UV_CACHE_DIR="$BASE/uv-cache"

if ! command -v uv >/dev/null; then
  echo "==> Installing uv (to ~/.local/bin)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Creating $ENV (Python 3.11)"
uv venv --quiet --python 3.11 "$ENV"
echo "==> Installing torch (CUDA build from PyPI) + pinned training stack"
VIRTUAL_ENV="$ENV" uv pip install --quiet torch -r "$TRAINING_DIR/requirements-train.txt"

echo "==> Registering Jupyter kernel 'PHA training'"
"$ENV/bin/python" -m ipykernel install --user --name pha-train --display-name "PHA training" >/dev/null
KERNEL_JSON="$("$ENV/bin/python" -c 'import jupyter_core.paths as p, os; print(os.path.join(p.jupyter_data_dir(), "kernels", "pha-train", "kernel.json"))')"
"$ENV/bin/python" - "$KERNEL_JSON" <<PY
import json, sys
path = sys.argv[1]
spec = json.load(open(path))
spec["env"] = {
    "HF_HOME": "$BASE/hf-cache",               # Phi-3 weights (~7.6 GB) land on /blue
    "PHA_WORK": "$TRAINING_DIR",               # notebook finds the pipeline files here
    "PHA_OUTPUT": "$BASE/runs",                # data splits, checkpoints, merged model, GGUFs
    "LLAMA_CPP_DIR": "$BASE/llama.cpp-b11347", # converter venv + build for export_gguf.sh
    "PATH": "$ENV/bin:" + "/usr/local/bin:/usr/bin:/bin",
}
json.dump(spec, open(path, "w"), indent=2)
PY

echo "==> Checking the stack"
"$ENV/bin/python" -c "import torch, transformers, peft, trl; print('torch', torch.__version__, '| CUDA build', torch.version.cuda, '| transformers', transformers.__version__, '| peft', peft.__version__, '| trl', trl.__version__)"
echo
echo "Done. In Open OnDemand, start Jupyter with a GPU, open $TRAINING_DIR/train_lora.ipynb,"
echo "and pick the kernel 'PHA training'. Outputs will go to $BASE/runs."
