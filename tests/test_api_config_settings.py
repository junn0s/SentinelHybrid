import os
from contextlib import contextmanager
from typing import Iterator

from src.api.config import ApiConfig


@contextmanager
def _temporary_env(values: dict[str, str]) -> Iterator[None]:
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, original in previous.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def test_settings_env_parsing_and_url_hydration() -> None:
    env_values = {
        "RAG_MCP_TRANSPORT": "streamable_http",
        "RAG_MCP_HOST": "10.0.0.10",
        "RAG_MCP_PORT": "9000",
        "RAG_MCP_PATH": "mcp",
        "RAG_MCP_ARGS": "-m src.mcp.rag_server",
        "OPS_MCP_TRANSPORT": "streamable_http",
        "OPS_MCP_HOST": "10.0.0.11",
        "OPS_MCP_PORT": "9001",
        "OPS_MCP_PATH": "/ops-mcp",
        "OPS_MCP_ARGS": "-m src.mcp.ops_server",
        "RAG_MCP_ENABLED": "false",
        "GEMINI_TTS_STYLE_PROMPT": "   ",
    }
    with _temporary_env(env_values):
        config = ApiConfig(_env_file=None)

    assert config.rag_mcp_enabled is False
    assert config.rag_mcp_args == ["-m", "src.mcp.rag_server"]
    assert config.ops_mcp_args == ["-m", "src.mcp.ops_server"]
    assert config.rag_mcp_url == "http://10.0.0.10:9000/mcp"
    assert config.ops_mcp_url == "http://10.0.0.11:9001/ops-mcp"
    assert config.gemini_tts_style_prompt is None


def test_from_env_compatibility_method() -> None:
    config = ApiConfig.from_env()
    assert isinstance(config, ApiConfig)
