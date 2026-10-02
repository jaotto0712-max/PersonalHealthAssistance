"""Run the backend with the validated bind address: `python -m pha [--reload]`."""

import sys

import uvicorn

from pha.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "pha.main:app", host=settings.host, port=settings.port, reload="--reload" in sys.argv
    )


if __name__ == "__main__":
    main()
