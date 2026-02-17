import os
import shlex
import sys
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    recents_max: int = 100
    event_log_path: str = "data/events/danger_events.jsonl"
    response_log_path: str = "data/events/danger_responses.jsonl"

    rag_top_k: int = 3
    rag_mcp_enabled: bool = True
    rag_mcp_timeout_sec: float = 10.0
    rag_mcp_tool_name: str = "retrieve_guidelines"
    rag_mcp_query_key: str = "query"
    rag_mcp_top_k_key: str = "top_k"

    rag_mcp_transport: str = "streamable_http"
    rag_mcp_command: str = "python3"
    rag_mcp_args: list[str] | None = None
    rag_mcp_url: str | None = None
    rag_mcp_host: str = "127.0.0.1"
    rag_mcp_port: int = 8765
    rag_mcp_path: str = "/mcp"
    rag_mcp_autostart: bool = True

    llm_provider: str = "gemini"
    gemini_model: str = "gemini-3-flash-preview"
    google_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "ApiConfig":
        args_str = os.getenv("RAG_MCP_ARGS", "-m src.mcp.rag_server")
        mcp_host = os.getenv("RAG_MCP_HOST", "127.0.0.1")
        mcp_port = int(os.getenv("RAG_MCP_PORT", "8765"))
        mcp_path = os.getenv("RAG_MCP_PATH", "/mcp")
        mcp_transport = os.getenv("RAG_MCP_TRANSPORT", "streamable_http")
        mcp_url = os.getenv("RAG_MCP_URL")
        if not mcp_url and mcp_transport == "streamable_http":
            normalized_path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
            mcp_url = f"http://{mcp_host}:{mcp_port}{normalized_path}"

        return cls(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            recents_max=int(os.getenv("API_RECENTS_MAX", "100")),
            event_log_path=os.getenv("EVENT_LOG_PATH", "data/events/danger_events.jsonl"),
            response_log_path=os.getenv("RESPONSE_LOG_PATH", "data/events/danger_responses.jsonl"),
            rag_top_k=int(os.getenv("RAG_TOP_K", "3")),
            rag_mcp_enabled=os.getenv("RAG_MCP_ENABLED", "true").lower() == "true",
            rag_mcp_timeout_sec=float(os.getenv("RAG_MCP_TIMEOUT_SEC", "10.0")),
            rag_mcp_tool_name=os.getenv("RAG_MCP_TOOL_NAME", "retrieve_guidelines"),
            rag_mcp_query_key=os.getenv("RAG_MCP_QUERY_KEY", "query"),
            rag_mcp_top_k_key=os.getenv("RAG_MCP_TOP_K_KEY", "top_k"),
            rag_mcp_transport=mcp_transport,
            rag_mcp_command=os.getenv("RAG_MCP_COMMAND", sys.executable),
            rag_mcp_args=shlex.split(args_str) if args_str else None,
            rag_mcp_url=mcp_url,
            rag_mcp_host=mcp_host,
            rag_mcp_port=mcp_port,
            rag_mcp_path=mcp_path,
            rag_mcp_autostart=os.getenv("RAG_MCP_AUTOSTART", "true").lower() == "true",
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
