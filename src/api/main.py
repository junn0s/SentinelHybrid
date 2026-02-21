from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.app_runtime import ApiRuntime
from src.api.config import ApiConfig
from src.api.repositories.event_repository import EventRepository
from src.api.routes.admin import router as admin_router
from src.api.routes.events import router as events_router
from src.api.routes.health import router as health_router
from src.api.services.gemini_tts import GeminiTTSGenerator
from src.api.services.llm_responder import LLMResponder
from src.api.services.local_rag import LocalRAGRetriever
from src.api.services.mcp_ops import MCPOperationsPublisher
from src.api.services.mcp_rag import MCPRAGRetriever
from src.api.services.pipeline import DangerProcessingPipeline


def build_runtime(config: ApiConfig | None = None) -> ApiRuntime:
    resolved = config or ApiConfig.from_env()
    pipeline = DangerProcessingPipeline(
        mcp_retriever=MCPRAGRetriever(resolved),
        local_retriever=LocalRAGRetriever(top_k=resolved.rag_top_k),
        responder=LLMResponder(resolved),
        tts_generator=GeminiTTSGenerator(resolved),
        mcp_timeout_sec=resolved.rag_mcp_timeout_sec,
    )
    return ApiRuntime(
        config=resolved,
        pipeline=pipeline,
        ops_publisher=MCPOperationsPublisher(resolved),
        repository=EventRepository(
            event_log_path=resolved.event_log_path,
            response_log_path=resolved.response_log_path,
            recents_max=resolved.recents_max,
        ),
        admin_dir=Path(__file__).resolve().parent / "static" / "admin",
    )


def create_app(runtime: ApiRuntime | None = None) -> FastAPI:
    app = FastAPI(title="SentinelHybrid Danger Event API", version="0.2.0")
    app.state.runtime = runtime or build_runtime()

    if app.state.runtime.admin_dir.exists():
        app.mount(
            "/admin/static",
            StaticFiles(directory=str(app.state.runtime.admin_dir)),
            name="admin-static",
        )

    app.include_router(admin_router)
    app.include_router(health_router)
    app.include_router(events_router)
    return app


app = create_app()
