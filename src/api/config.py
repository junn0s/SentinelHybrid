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
    rag_mcp_timeout_sec: float = 2.0
    rag_mcp_tool_name: str = "retrieve_guidelines"
    rag_mcp_query_key: str = "query"
    rag_mcp_top_k_key: str = "top_k"

    rag_mcp_transport: str = "stdio"
    rag_mcp_command: str = "python3"
    rag_mcp_args: list[str] | None = None
    rag_mcp_url: str | None = None

    llm_provider: str = "gemini"
    gemini_model: str = "gemini-3-flash-preview"
    google_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "ApiConfig":
        args_str = os.getenv("RAG_MCP_ARGS", "-m src.mcp.rag_server")
        return cls(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            recents_max=int(os.getenv("API_RECENTS_MAX", "100")),
            event_log_path=os.getenv("EVENT_LOG_PATH", "data/events/danger_events.jsonl"),
            response_log_path=os.getenv("RESPONSE_LOG_PATH", "data/events/danger_responses.jsonl"),
            rag_top_k=int(os.getenv("RAG_TOP_K", "3")),
            rag_mcp_enabled=os.getenv("RAG_MCP_ENABLED", "true").lower() == "true",
            rag_mcp_timeout_sec=float(os.getenv("RAG_MCP_TIMEOUT_SEC", "2.0")),
            rag_mcp_tool_name=os.getenv("RAG_MCP_TOOL_NAME", "retrieve_guidelines"),
            rag_mcp_query_key=os.getenv("RAG_MCP_QUERY_KEY", "query"),
            rag_mcp_top_k_key=os.getenv("RAG_MCP_TOP_K_KEY", "top_k"),
            rag_mcp_transport=os.getenv("RAG_MCP_TRANSPORT", "stdio"),
            rag_mcp_command=os.getenv("RAG_MCP_COMMAND", sys.executable),
            rag_mcp_args=shlex.split(args_str) if args_str else None,
            rag_mcp_url=os.getenv("RAG_MCP_URL"),
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
