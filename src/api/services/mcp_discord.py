import asyncio
import logging
from typing import Any

from src.api.config import ApiConfig
from src.api.models import DangerEvent, DangerResponse
from src.api.services.mcp_base import MCPToolClient, normalize_mcp_result


class MCPOperationsPublisher:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._tool_client = MCPToolClient(
            server_alias="ops",
            transport=self.config.ops_mcp_transport,
            url=self.config.ops_mcp_url,
            command=self.config.ops_mcp_command,
            args=self.config.ops_mcp_args or ["-m", "src.mcp.ops_server"],
            logger=self.logger,
            import_log_message="langchain-mcp-adapters unavailable for ops publish",
        )

    async def _get_tool(self, tool_name: str):
        try:
            selected = await self._tool_client.get_tool(tool_name=tool_name, fallback_first=False)
            if selected is None:
                self.logger.warning("MCP ops tool not found: %s", tool_name)
            return selected
        except Exception as exc:
            self.logger.warning("MCP ops tool discovery failed: %s", exc)
            return None

    async def _invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool = await self._get_tool(tool_name)
        if tool is None:
            return {"status": "tool-unavailable", "tool": tool_name}

        try:
            raw = await asyncio.wait_for(
                tool.ainvoke(payload),
                timeout=self.config.ops_mcp_timeout_sec,
            )
            normalized = self._normalize(raw)
            if isinstance(normalized, dict):
                return normalized
            return {"status": "ok", "result": normalized}
        except Exception as exc:
            self.logger.warning("MCP ops invoke failed. tool=%s err=%s", tool_name, exc)
            return {"status": "error", "tool": tool_name, "error": str(exc)}

    def _normalize(self, raw: Any) -> Any:
        normalized = normalize_mcp_result(raw)
        if normalized is None:
            return {"status": "ok"}
        if isinstance(normalized, dict):
            return normalized
        if isinstance(normalized, str):
            return {"status": "ok", "message": normalized}
        return {"status": "ok", "result": str(normalized)}

    def _discord_text(self, event: DangerEvent, response: DangerResponse) -> str:
        return (
            "[SentinelHybrid] 위험 이벤트 감지\n"
            f"- event_id: {event.event_id}\n"
            f"- source: {event.source}\n"
            f"- summary: {event.summary}\n"
            f"- rag_source: {response.rag_source}\n"
            f"- tts: {response.jetson_tts_summary}"
        )

    async def publish(self, event: DangerEvent, response: DangerResponse) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not self.config.ops_mcp_enabled:
            return {"status": "disabled"}

        jobs: list[tuple[str, Any]] = []
        if self.config.ops_mcp_discord_enabled:
            payload = {
                "text": self._discord_text(event, response),
                "event_id": event.event_id,
                "severity": "danger",
            }
            jobs.append(("discord", self._invoke(self.config.ops_mcp_discord_tool_name, payload)))
        else:
            result["discord"] = {"status": "disabled"}

        if jobs:
            outputs = await asyncio.gather(*(job for _, job in jobs), return_exceptions=True)
            for (channel, _), output in zip(jobs, outputs):
                if isinstance(output, Exception):
                    result[channel] = {"status": "error", "error": str(output)}
                    continue
                result[channel] = output

        return result
