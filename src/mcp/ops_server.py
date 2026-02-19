import os

from pydantic import BaseModel, Field, ValidationError

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("fastmcp is required to run the MCP Ops server.") from exc

mcp = FastMCP("SentinelHybridOps")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_TIMEOUT_SEC = float(os.getenv("DISCORD_TIMEOUT_SEC", "6"))


class DiscordAlertInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    event_id: str = ""
    severity: str = "danger"


class ToolResult(BaseModel):
    status: str
    reason: str | None = None
    http_status: int | None = None
    body: str | None = None
    error: str | None = None


@mcp.tool
def discord_send_alert(text: str, event_id: str = "", severity: str = "danger") -> dict:
    try:
        req = DiscordAlertInput.model_validate(
            {
                "text": text,
                "event_id": event_id,
                "severity": severity,
            }
        )
    except ValidationError as exc:
        return ToolResult(status="error", reason=f"invalid discord alert input: {exc}").model_dump(mode="json")

    if not DISCORD_WEBHOOK_URL:
        return ToolResult(status="skipped", reason="DISCORD_WEBHOOK_URL is not configured").model_dump(mode="json")

    try:
        import requests
    except Exception as exc:
        return ToolResult(status="error", reason=f"requests import failed: {exc}").model_dump(mode="json")

    payload = {"content": req.text}
    if req.event_id:
        payload["content"] = f"{req.text}\n(event_id={req.event_id}, severity={req.severity})"

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=DISCORD_TIMEOUT_SEC,
        )
        if response.ok:
            return ToolResult(status="ok", http_status=response.status_code).model_dump(mode="json")
        return ToolResult(
            status="error",
            http_status=response.status_code,
            body=response.text[:300],
        ).model_dump(mode="json")
    except Exception as exc:
        return ToolResult(status="error", error=str(exc)).model_dump(mode="json")


if __name__ == "__main__":
    transport = os.getenv("OPS_SERVER_MCP_TRANSPORT", os.getenv("SENTINEL_MCP_TRANSPORT", "stdio"))
    if transport == "streamable-http":
        host = os.getenv("OPS_SERVER_MCP_HOST", os.getenv("SENTINEL_MCP_HOST", "127.0.0.1"))
        port = int(os.getenv("OPS_SERVER_MCP_PORT", os.getenv("SENTINEL_MCP_PORT", "8766")))
        path = os.getenv("OPS_SERVER_MCP_PATH", os.getenv("SENTINEL_MCP_PATH", "/mcp"))
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            path=path,
            show_banner=False,
        )
    else:
        mcp.run(transport="stdio", show_banner=False)
