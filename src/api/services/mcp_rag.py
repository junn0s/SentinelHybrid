import logging
import json
from typing import Any

from src.api.config import ApiConfig
from src.api.models import RAGReference


class MCPRAGRetriever:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client = None
        self._tool = None

    async def _get_tool(self):
        if self._tool is not None:
            return self._tool

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except Exception as exc:  # pragma: no cover
            self.logger.warning("langchain-mcp-adapters unavailable: %s", exc)
            return None

        server_cfg: dict[str, Any]
        if self.config.rag_mcp_transport == "streamable_http" and self.config.rag_mcp_url:
            server_cfg = {
                "transport": "streamable_http",
                "url": self.config.rag_mcp_url,
            }
        else:
            server_cfg = {
                "transport": "stdio",
                "command": self.config.rag_mcp_command,
                "args": self.config.rag_mcp_args or ["-m", "src.mcp.rag_server"],
            }

        try:
            self._client = MultiServerMCPClient({"rag": server_cfg})
            tools = await self._client.get_tools()
            if not tools:
                return None

            selected = None
            for tool in tools:
                if tool.name == self.config.rag_mcp_tool_name:
                    selected = tool
                    break
            if selected is None:
                selected = tools[0]

            self._tool = selected
            return self._tool
        except Exception as exc:
            self.logger.warning("MCP tool init failed: %s", exc)
            self._client = None
            self._tool = None
            return None

    async def retrieve(self, query: str) -> list[RAGReference]:
        if not self.config.rag_mcp_enabled:
            return []

        selected = await self._get_tool()
        if selected is None:
            return []

        try:
            payload = {
                self.config.rag_mcp_query_key: query,
                self.config.rag_mcp_top_k_key: self.config.rag_top_k,
            }
            raw = await selected.ainvoke(payload)
            return self._normalize(raw)
        except Exception as exc:
            self.logger.warning("MCP retrieval failed: %s", exc)
            return []

    def _normalize(self, raw: Any) -> list[RAGReference]:
        if isinstance(raw, list):
            # FastMCP returns content blocks, e.g. [{"type":"text","text":"{...json...}"}]
            for item in raw:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    text = item["text"].strip()
                    try:
                        parsed = json.loads(text)
                        return self._normalize(parsed)
                    except Exception:
                        return [RAGReference(id="mcp-text", title="MCP Result", content=text, tags=[])]
            return []

        if isinstance(raw, str):
            return [RAGReference(id="mcp-text", title="MCP Result", content=raw, tags=[])]

        if not isinstance(raw, dict):
            return []

        matches = raw.get("matches")
        if not isinstance(matches, list):
            return []

        refs: list[RAGReference] = []
        for idx, item in enumerate(matches):
            if not isinstance(item, dict):
                continue
            refs.append(
                RAGReference(
                    id=str(item.get("id", f"mcp-{idx}")),
                    title=str(item.get("title", "RAG Match")),
                    content=str(item.get("content", "")),
                    tags=[str(tag) for tag in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
                )
            )
        return refs
