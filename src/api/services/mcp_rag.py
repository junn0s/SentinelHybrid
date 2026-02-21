import logging
from typing import Any

from src.api.config import ApiConfig
from src.api.models import RAGReference
from src.api.services.mcp_base import MCPToolClient, normalize_mcp_result


class MCPRAGRetriever:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._tool_client = MCPToolClient(
            server_alias="rag",
            transport=self.config.rag_mcp_transport,
            url=self.config.rag_mcp_url,
            command=self.config.rag_mcp_command,
            args=self.config.rag_mcp_args or ["-m", "src.mcp.rag_server"],
            logger=self.logger,
            import_log_message="langchain-mcp-adapters unavailable",
        )
        self._tool = None

    async def _get_tool(self):
        if self._tool is not None:
            return self._tool

        try:
            selected = await self._tool_client.get_tool(
                tool_name=self.config.rag_mcp_tool_name,
                fallback_first=True,
            )
            if selected is None:
                return None
            self._tool = selected
            return self._tool
        except Exception as exc:
            self.logger.warning("MCP tool init failed: %s", exc)
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
        normalized = normalize_mcp_result(raw)
        if normalized is None:
            return []

        if isinstance(normalized, str):
            return [RAGReference(id="mcp-text", title="MCP Result", content=normalized, tags=[])]

        if not isinstance(normalized, dict):
            return []

        matches = normalized.get("matches")
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
