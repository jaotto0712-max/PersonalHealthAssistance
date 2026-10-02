"""One-time download of the local embedding model (the only step that needs the network).

    cd backend && uv run python scripts/fetch_embeddings.py

The app itself runs with HF_HUB_OFFLINE=1 and loads the model from PHA_EMBED_MODEL_DIR.
Deliberately does not import `pha`, because importing it switches Hugging Face to offline mode.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "BAAI/bge-small-en-v1.5"
DEFAULT_DIR = REPO_ROOT / "models" / "embeddings" / "bge-small-en-v1.5"


def main() -> None:
    target = Path(os.environ.get("PHA_EMBED_MODEL_DIR", DEFAULT_DIR))
    if (target / "config.json").is_file():
        print(f"Embedding model already present at {target}")
        return
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import snapshot_download

    print(f"Downloading {MODEL_ID} to {target} ...")
    snapshot_download(
        MODEL_ID,
        local_dir=target,
        allow_patterns=["*.json", "*.txt", "model.safetensors", "1_Pooling/*", "modules.json"],
    )
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
