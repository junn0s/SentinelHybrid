import shlex
import sys
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    port: int = Field(default=8000, validation_alias="API_PORT")
    recents_max: int = Field(default=100, validation_alias="API_RECENTS_MAX")
    event_log_path: str = Field(default="data/events/danger_events.jsonl", validation_alias="EVENT_LOG_PATH")
    response_log_path: str = Field(default="data/events/danger_responses.jsonl", validation_alias="RESPONSE_LOG_PATH")

    rag_top_k: int = Field(default=3, validation_alias="RAG_TOP_K")
    rag_mcp_enabled: bool = Field(default=True, validation_alias="RAG_MCP_ENABLED")
    rag_mcp_timeout_sec: float = Field(default=10.0, validation_alias="RAG_MCP_TIMEOUT_SEC")
    rag_mcp_tool_name: str = Field(default="retrieve_guidelines", validation_alias="RAG_MCP_TOOL_NAME")
    rag_mcp_query_key: str = Field(default="query", validation_alias="RAG_MCP_QUERY_KEY")
    rag_mcp_top_k_key: str = Field(default="top_k", validation_alias="RAG_MCP_TOP_K_KEY")

    rag_mcp_transport: str = Field(default="streamable_http", validation_alias="RAG_MCP_TRANSPORT")
    rag_mcp_command: str = Field(default=sys.executable, validation_alias="RAG_MCP_COMMAND")
    rag_mcp_args: list[str] | None = Field(default_factory=lambda: ["-m", "src.mcp.rag_server"], validation_alias="RAG_MCP_ARGS")
    rag_mcp_url: str | None = Field(default=None, validation_alias="RAG_MCP_URL")
    rag_mcp_host: str = Field(default="127.0.0.1", validation_alias="RAG_MCP_HOST")
    rag_mcp_port: int = Field(default=8765, validation_alias="RAG_MCP_PORT")
    rag_mcp_path: str = Field(default="/mcp", validation_alias="RAG_MCP_PATH")

    ops_mcp_enabled: bool = Field(default=True, validation_alias="OPS_MCP_ENABLED")
    ops_mcp_timeout_sec: float = Field(default=8.0, validation_alias="OPS_MCP_TIMEOUT_SEC")
    ops_mcp_discord_enabled: bool = Field(default=True, validation_alias="OPS_MCP_DISCORD_ENABLED")
    ops_mcp_discord_tool_name: str = Field(default="discord_send_alert", validation_alias="OPS_MCP_DISCORD_TOOL_NAME")
    ops_mcp_transport: str = Field(default="streamable_http", validation_alias="OPS_MCP_TRANSPORT")
    ops_mcp_command: str = Field(default=sys.executable, validation_alias="OPS_MCP_COMMAND")
    ops_mcp_args: list[str] | None = Field(default_factory=lambda: ["-m", "src.mcp.ops_server"], validation_alias="OPS_MCP_ARGS")
    ops_mcp_url: str | None = Field(default=None, validation_alias="OPS_MCP_URL")
    ops_mcp_host: str = Field(default="127.0.0.1", validation_alias="OPS_MCP_HOST")
    ops_mcp_port: int = Field(default=8766, validation_alias="OPS_MCP_PORT")
    ops_mcp_path: str = Field(default="/mcp", validation_alias="OPS_MCP_PATH")

    llm_provider: str = Field(default="gemini", validation_alias="LLM_PROVIDER")
    gemini_model: str = Field(default="gemini-3-flash-preview", validation_alias="GEMINI_MODEL")
    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    gemini_tts_enabled: bool = Field(default=True, validation_alias="GEMINI_TTS_ENABLED")
    gemini_tts_model: str = Field(default="gemini-2.5-flash-preview-tts", validation_alias="GEMINI_TTS_MODEL")
    gemini_tts_voice: str = Field(default="Kore", validation_alias="GEMINI_TTS_VOICE")
    gemini_tts_style_prompt: str | None = Field(default=None, validation_alias="GEMINI_TTS_STYLE_PROMPT")
    gemini_tts_rate_hz: int = Field(default=24000, validation_alias="GEMINI_TTS_RATE_HZ")
    gemini_tts_channels: int = Field(default=1, validation_alias="GEMINI_TTS_CHANNELS")
    gemini_tts_sample_width: int = Field(default=2, validation_alias="GEMINI_TTS_SAMPLE_WIDTH")

    @field_validator("rag_mcp_args", "ops_mcp_args", mode="before")
    @classmethod
    def _parse_command_args(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return shlex.split(stripped) if stripped else None
        if isinstance(value, list):
            return [str(item) for item in value]
        return None

    @field_validator("gemini_tts_style_prompt", mode="before")
    @classmethod
    def _normalize_style_prompt(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _hydrate_default_urls(self) -> "ApiConfig":
        if not self.rag_mcp_url and self.rag_mcp_transport == "streamable_http":
            normalized_path = self.rag_mcp_path if self.rag_mcp_path.startswith("/") else f"/{self.rag_mcp_path}"
            self.rag_mcp_url = f"http://{self.rag_mcp_host}:{self.rag_mcp_port}{normalized_path}"

        if not self.ops_mcp_url and self.ops_mcp_transport == "streamable_http":
            normalized_path = self.ops_mcp_path if self.ops_mcp_path.startswith("/") else f"/{self.ops_mcp_path}"
            self.ops_mcp_url = f"http://{self.ops_mcp_host}:{self.ops_mcp_port}{normalized_path}"

        return self

    @classmethod
    def from_env(cls) -> "ApiConfig":
        return cls()
