from typing import Any

from fastapi import APIRouter, Depends

from src.api.app_runtime import ApiRuntime
from src.api.routes.deps import get_runtime

router = APIRouter()


@router.get("/health")
def health(runtime: ApiRuntime = Depends(get_runtime)) -> dict[str, Any]:
    config = runtime.config
    return {
        "status": "ok",
        "rag_mcp_enabled": config.rag_mcp_enabled,
        "llm_provider": config.llm_provider,
        "gemini_model": config.gemini_model,
    }
