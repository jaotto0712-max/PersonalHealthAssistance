from typing import Any

from fastapi import APIRouter, Request

from pha import __version__

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Backend liveness plus model availability (`llm`: ok | unavailable | model_missing)."""
    result: dict[str, Any] = {"status": "ok", "version": __version__}
    llm = getattr(request.app.state, "llm", None)
    if llm is not None:
        status = await llm.health()
        result |= {"llm": status.status, "model": status.model}
        if status.hint:
            result["hint"] = status.hint
    return result
