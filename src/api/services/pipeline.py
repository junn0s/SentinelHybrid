import asyncio

from src.api.models import DangerEvent, DangerResponse
from src.api.services.llm_responder import LLMResponder
from src.api.services.local_rag import LocalRAGRetriever
from src.api.services.mcp_rag import MCPRAGRetriever


class DangerProcessingPipeline:
    def __init__(
        self,
        mcp_retriever: MCPRAGRetriever,
        local_retriever: LocalRAGRetriever,
        responder: LLMResponder,
        mcp_timeout_sec: float = 2.0,
    ) -> None:
        self.mcp_retriever = mcp_retriever
        self.local_retriever = local_retriever
        self.responder = responder
        self.mcp_timeout_sec = mcp_timeout_sec

    async def process(self, event: DangerEvent) -> DangerResponse:
        try:
            refs = await asyncio.wait_for(
                self.mcp_retriever.retrieve(event.summary),
                timeout=self.mcp_timeout_sec,
            )
        except Exception:
            refs = []
        rag_source = "mcp"
        if not refs:
            refs = self.local_retriever.retrieve(event.summary)
            rag_source = "local-fallback"

        operator_response, jetson_summary = await self.responder.build_response(
            situation=event.summary,
            references=refs,
        )

        return DangerResponse(
            event_id=event.event_id,
            rag_source=rag_source,
            llm_provider=self.responder.provider_name,
            operator_response=operator_response,
            jetson_tts_summary=jetson_summary,
            references=refs,
        )
