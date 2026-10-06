"""Command-line entry point for lora_pipeline.train, used for multi-GPU data-parallel runs:

    python -m torch.distributed.run --standalone --nproc_per_node=2 train_cli.py --config run.json

The notebook calls this through lora_pipeline.train_multi_gpu(); you rarely run it by hand.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lora_pipeline as lp  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="JSON dump of a TrainConfig")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    cfg = lp.TrainConfig(**json.loads(args.config.read_text()))
    lp.train(cfg, resume=not args.no_resume)


if __name__ == "__main__":
    main()
