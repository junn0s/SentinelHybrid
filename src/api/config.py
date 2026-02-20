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

    ops_mcp_enabled: bool = True
    ops_mcp_timeout_sec: float = 8.0
    ops_mcp_discord_enabled: bool = True
    ops_mcp_discord_tool_name: str = "discord_send_alert"
    ops_mcp_transport: str = "streamable_http"
    ops_mcp_command: str = "python3"
    ops_mcp_args: list[str] | None = None
    ops_mcp_url: str | None = None
    ops_mcp_host: str = "127.0.0.1"
    ops_mcp_port: int = 8766
    ops_mcp_path: str = "/mcp"

    llm_provider: str = "gemini"
    gemini_model: str = "gemini-3-flash-preview"
    google_api_key: str | None = None
    gemini_tts_enabled: bool = True
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_tts_voice: str = "Kore"
    gemini_tts_style_prompt: str | None = None
    gemini_tts_rate_hz: int = 24000
    gemini_tts_channels: int = 1
    gemini_tts_sample_width: int = 2

    @classmethod
    def from_env(cls) -> "ApiConfig":
        rag_args_str = os.getenv("RAG_MCP_ARGS", "-m src.mcp.rag_server")
        rag_mcp_host = os.getenv("RAG_MCP_HOST", "127.0.0.1")
        rag_mcp_port = int(os.getenv("RAG_MCP_PORT", "8765"))
        rag_mcp_path = os.getenv("RAG_MCP_PATH", "/mcp")
        rag_mcp_transport = os.getenv("RAG_MCP_TRANSPORT", "streamable_http")
        rag_mcp_url = os.getenv("RAG_MCP_URL")
        if not rag_mcp_url and rag_mcp_transport == "streamable_http":
            normalized_path = rag_mcp_path if rag_mcp_path.startswith("/") else f"/{rag_mcp_path}"
            rag_mcp_url = f"http://{rag_mcp_host}:{rag_mcp_port}{normalized_path}"

        ops_args_str = os.getenv("OPS_MCP_ARGS", "-m src.mcp.ops_server")
        ops_mcp_host = os.getenv("OPS_MCP_HOST", "127.0.0.1")
        ops_mcp_port = int(os.getenv("OPS_MCP_PORT", "8766"))
        ops_mcp_path = os.getenv("OPS_MCP_PATH", "/mcp")
        ops_mcp_transport = os.getenv("OPS_MCP_TRANSPORT", "streamable_http")
        ops_mcp_url = os.getenv("OPS_MCP_URL")
        if not ops_mcp_url and ops_mcp_transport == "streamable_http":
            normalized_path = ops_mcp_path if ops_mcp_path.startswith("/") else f"/{ops_mcp_path}"
            ops_mcp_url = f"http://{ops_mcp_host}:{ops_mcp_port}{normalized_path}"

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
            rag_mcp_transport=rag_mcp_transport,
            rag_mcp_command=os.getenv("RAG_MCP_COMMAND", sys.executable),
            rag_mcp_args=shlex.split(rag_args_str) if rag_args_str else None,
            rag_mcp_url=rag_mcp_url,
            rag_mcp_host=rag_mcp_host,
            rag_mcp_port=rag_mcp_port,
            rag_mcp_path=rag_mcp_path,
            rag_mcp_autostart=os.getenv("RAG_MCP_AUTOSTART", "true").lower() == "true",
            ops_mcp_enabled=os.getenv("OPS_MCP_ENABLED", "true").lower() == "true",
            ops_mcp_timeout_sec=float(os.getenv("OPS_MCP_TIMEOUT_SEC", "8.0")),
            ops_mcp_discord_enabled=os.getenv("OPS_MCP_DISCORD_ENABLED", "true").lower() == "true",
            ops_mcp_discord_tool_name=os.getenv("OPS_MCP_DISCORD_TOOL_NAME", "discord_send_alert"),
            ops_mcp_transport=ops_mcp_transport,
            ops_mcp_command=os.getenv("OPS_MCP_COMMAND", sys.executable),
            ops_mcp_args=shlex.split(ops_args_str) if ops_args_str else None,
            ops_mcp_url=ops_mcp_url,
            ops_mcp_host=ops_mcp_host,
            ops_mcp_port=ops_mcp_port,
            ops_mcp_path=ops_mcp_path,
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            gemini_tts_enabled=os.getenv("GEMINI_TTS_ENABLED", "true").lower() == "true",
            gemini_tts_model=os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            gemini_tts_voice=os.getenv("GEMINI_TTS_VOICE", "Kore"),
            gemini_tts_style_prompt=(os.getenv("GEMINI_TTS_STYLE_PROMPT") or "").strip() or None,
            gemini_tts_rate_hz=int(os.getenv("GEMINI_TTS_RATE_HZ", "24000")),
            gemini_tts_channels=int(os.getenv("GEMINI_TTS_CHANNELS", "1")),
            gemini_tts_sample_width=int(os.getenv("GEMINI_TTS_SAMPLE_WIDTH", "2")),
        )
