import asyncio
import json
import logging
from typing import Any


def normalize_mcp_result(raw: Any) -> Any:
    if isinstance(raw, list):
        # FastMCP often returns content blocks, e.g. [{"type":"text","text":"{...json...}"}]
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text = item["text"].strip()
                try:
                    return json.loads(text)
                except Exception:
                    return text
        return None

    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return raw

    return raw


class MCPToolClient:
    def __init__(
        self,
        *,
        server_alias: str,
        transport: str,
        url: str | None,
        command: str,
        args: list[str] | None,
        logger: logging.Logger,
        import_log_message: str,
    ) -> None:
        self.server_alias = server_alias
        self.transport = transport
        self.url = url
        self.command = command
        self.args = args
        self.logger = logger
        self.import_log_message = import_log_message
        self._client = None
        self._tools: dict[str, Any] = {}
        self._tool_lock = asyncio.Lock()

    def _server_cfg(self) -> dict[str, Any]:
        if self.transport == "streamable_http" and self.url:
            return {
                "transport": "streamable_http",
                "url": self.url,
            }
        return {
            "transport": "stdio",
            "command": self.command,
            "args": self.args or [],
        }

    async def _ensure_client(self):
        if self._client is not None:
            return self._client

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except Exception as exc:  # pragma: no cover
            self.logger.warning("%s: %s", self.import_log_message, exc)
            return None

        self._client = MultiServerMCPClient({self.server_alias: self._server_cfg()})
        return self._client

    async def get_tool(self, tool_name: str | None = None, fallback_first: bool = False):
        if tool_name and tool_name in self._tools:
            return self._tools[tool_name]

        async with self._tool_lock:
            if tool_name and tool_name in self._tools:
                return self._tools[tool_name]

            client = await self._ensure_client()
            if client is None:
                return None

            tools = await client.get_tools()
            if not tools:
                return None

            for tool in tools:
                self._tools[tool.name] = tool

            if tool_name:
                selected = self._tools.get(tool_name)
                if selected is None and fallback_first:
                    selected = tools[0]
                return selected

            return tools[0]

    async def invoke(self, tool_name: str, payload: dict[str, Any], timeout_sec: float | None = None) -> Any:
        tool = await self.get_tool(tool_name=tool_name, fallback_first=False)
        if tool is None:
            raise RuntimeError(f"tool-unavailable:{tool_name}")
        if timeout_sec is not None:
            return await asyncio.wait_for(tool.ainvoke(payload), timeout=timeout_sec)
        return await tool.ainvoke(payload)
