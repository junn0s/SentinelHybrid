from src.api.models import RAGReference
from src.rag.manual_repository import load_manuals, search_manuals


class LocalRAGRetriever:
    def __init__(self, top_k: int = 3) -> None:
        self.top_k = top_k
        self.manuals = load_manuals()

    def retrieve(self, query: str) -> list[RAGReference]:
        results = search_manuals(query=query, manuals=self.manuals, top_k=self.top_k)
        return [
            RAGReference(
                id=item.id,
                title=item.title,
                content=item.content,
                tags=item.tags,
            )
            for item in results
        ]

