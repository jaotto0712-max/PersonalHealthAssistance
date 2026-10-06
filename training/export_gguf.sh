#!/usr/bin/env bash
# Convert a Hugging Face model (directory or hub id) to a quantized GGUF for Ollama.
#
#   training/export_gguf.sh <hf_dir_or_id> <name> [out_dir]
#
#   training/export_gguf.sh outputs/phi3-medquad-merged phi3-medquad          # fine-tuned
#   training/export_gguf.sh microsoft/Phi-3-mini-4k-instruct phi3-base       # baseline
#
# Writes <out_dir>/<name>-<QUANT>.gguf (default out_dir: models/). With REGISTER=1 and
# models/Modelfile.<name without "phi3-"> present, also runs `ollama create <name>`.
#
# Env: QUANT (default Q4_K_M), LLAMA_CPP_REF (pinned), LLAMA_CPP_DIR (cache), KEEP_F16=1, REGISTER=1
set -euo pipefail

LLAMA_CPP_REF="${LLAMA_CPP_REF:-b11347}"
QUANT="${QUANT:-Q4_K_M}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:?usage: export_gguf.sh <hf_dir_or_id> <name> [out_dir]}"
NAME="${2:?usage: export_gguf.sh <hf_dir_or_id> <name> [out_dir]}"
OUT="${3:-$REPO_ROOT/models}"
CACHE="${LLAMA_CPP_DIR:-$HOME/.cache/pha/llama.cpp-$LLAMA_CPP_REF}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

# 1. llama.cpp at a pinned release (converter script + quantize tool must match).
if [[ ! -f "$CACHE/convert_hf_to_gguf.py" ]]; then
  log "Cloning llama.cpp $LLAMA_CPP_REF"
  git clone --quiet --depth 1 --branch "$LLAMA_CPP_REF" https://github.com/ggml-org/llama.cpp "$CACHE"
fi
if [[ ! -x "$CACHE/.venv/bin/python" ]]; then
  log "Installing converter dependencies"
  python3 -m venv "$CACHE/.venv"
  "$CACHE/.venv/bin/pip" install --quiet --upgrade pip
  "$CACHE/.venv/bin/pip" install --quiet -r "$CACHE/requirements/requirements-convert_hf_to_gguf.txt" huggingface_hub
fi
PY="$CACHE/.venv/bin/python"
QUANTIZE="$CACHE/build/bin/llama-quantize"
if [[ ! -x "$QUANTIZE" ]]; then
  log "Building llama-quantize"
  # GGML_NATIVE=OFF: portable build. Native builds target the build host's newest CPU
  # instructions (e.g. AVX-VNNI on AMD Turin), which older system assemblers can't encode
  # ("unsupported instruction vpdpbusd"). llama-quantize is a one-off tool; speed is irrelevant.
  rm -rf "$CACHE/build"
  cmake -S "$CACHE" -B "$CACHE/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF >/dev/null
  cmake --build "$CACHE/build" --target llama-quantize -j >/dev/null
fi

# 2. Resolve the source model (hub ids are downloaded once into the cache).
if [[ -d "$SRC" ]]; then
  MODEL_DIR="$(cd "$SRC" && pwd)"
else
  MODEL_DIR="$CACHE/hf/$NAME"
  if [[ ! -f "$MODEL_DIR/config.json" ]]; then
    log "Downloading $SRC"
    HF_HUB_OFFLINE=0 "$PY" -c "from huggingface_hub import snapshot_download as s; s('$SRC', local_dir='$MODEL_DIR', allow_patterns=['*.json','*.safetensors','*.model','*.txt','*.py'])"
  fi
fi

# 3. HF → f16 GGUF → quantized GGUF.
mkdir -p "$OUT"
F16="$OUT/$NAME-f16.gguf"
FINAL="$OUT/$NAME-$QUANT.gguf"
log "Converting $MODEL_DIR → $F16"
"$PY" "$CACHE/convert_hf_to_gguf.py" "$MODEL_DIR" --outtype f16 --outfile "$F16" >/dev/null
log "Quantizing → $FINAL ($QUANT)"
"$QUANTIZE" "$F16" "$FINAL" "$QUANT" >/dev/null 2>&1
[[ "${KEEP_F16:-0}" == "1" ]] || rm -f "$F16"
log "Wrote $FINAL ($(du -h "$FINAL" | cut -f1))"

# 4. Optionally register with the local Ollama.
MODELFILE="$REPO_ROOT/models/Modelfile.${NAME#phi3-}"
if [[ "${REGISTER:-0}" == "1" ]]; then
  [[ -f "$MODELFILE" ]] || { echo "No $MODELFILE to register $NAME with" >&2; exit 1; }
  [[ "$(cd "$OUT" && pwd)" == "$REPO_ROOT/models" ]] || cp "$FINAL" "$REPO_ROOT/models/"
  log "ollama create $NAME"
  (cd "$REPO_ROOT/models" && ollama create "$NAME" -f "$MODELFILE")
fi
