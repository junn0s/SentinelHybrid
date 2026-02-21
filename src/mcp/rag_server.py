import logging
import os

from src.rag.manual_repository import load_manuals, search_manuals

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("fastmcp is required to run the MCP RAG server.") from exc

mcp = FastMCP("SentinelHybridRAG")
MANUALS = load_manuals()
CHROMA_COLLECTION = None
LOGGER = logging.getLogger(__name__)

RAG_CHROMA_PATH = os.getenv("RAG_CHROMA_PATH", "data/chroma")
RAG_CHROMA_COLLECTION = os.getenv("RAG_CHROMA_COLLECTION", "sentinelhybrid_manuals_e5_small")
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
RAG_EMBEDDING_DEVICE = os.getenv("RAG_EMBEDDING_DEVICE", "cpu")


def _is_e5_model() -> bool:
    return "e5" in RAG_EMBEDDING_MODEL.lower()


def _prepare_document_text(text: str) -> str:
    if _is_e5_model():
        return f"passage: {text}"
    return text


def _prepare_query_text(text: str) -> str:
    if _is_e5_model():
        return f"query: {text}"
    return text


def _cleanup_document_text(text: str) -> str:
    if _is_e5_model() and text.startswith("passage: "):
        return text[len("passage: ") :]
    return text


def _build_embedding_function():
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction  # type: ignore

        LOGGER.info(
            "Using embedding model for RAG: model=%s device=%s",
            RAG_EMBEDDING_MODEL,
            RAG_EMBEDDING_DEVICE,
        )
        return SentenceTransformerEmbeddingFunction(
            model_name=RAG_EMBEDDING_MODEL,
            device=RAG_EMBEDDING_DEVICE,
            normalize_embeddings=True,
        )
    except Exception as exc:
        LOGGER.warning("Embedding function init failed. Falling back to Chroma default embedding: %s", exc)
        return None


def _init_chroma() -> None:
    global CHROMA_COLLECTION
    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path=RAG_CHROMA_PATH)
        embedding_fn = _build_embedding_function()
        if embedding_fn is not None:
            collection = client.get_or_create_collection(
                name=RAG_CHROMA_COLLECTION,
                embedding_function=embedding_fn,
            )
        else:
            collection = client.get_or_create_collection(name=RAG_CHROMA_COLLECTION)

        # Keep manual entries synchronized.
        collection.upsert(
            ids=[m.id for m in MANUALS],
            documents=[_prepare_document_text(m.content) for m in MANUALS],
            metadatas=[{"title": m.title, "tags": ",".join(m.tags)} for m in MANUALS],
        )

        CHROMA_COLLECTION = collection
    except Exception as exc:
        LOGGER.warning("Chroma init failed. Keyword fallback only: %s", exc)
        CHROMA_COLLECTION = None


_init_chroma()


@mcp.tool
def retrieve_guidelines(query: str, top_k: int = 3) -> dict:
    matches = []
    if CHROMA_COLLECTION is not None:
        try:
            result = CHROMA_COLLECTION.query(query_texts=[_prepare_query_text(query)], n_results=top_k)
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            for idx, item_id in enumerate(ids):
                meta = metas[idx] if idx < len(metas) else {}
                tags = []
                if isinstance(meta, dict) and isinstance(meta.get("tags"), str):
                    tags = [t for t in meta["tags"].split(",") if t]
                matches.append(
                    {
                        "id": str(item_id),
                        "title": str(meta.get("title", "RAG Match")) if isinstance(meta, dict) else "RAG Match",
                        "content": _cleanup_document_text(str(docs[idx])) if idx < len(docs) else "",
                        "tags": tags,
                    }
                )
        except Exception as exc:
            LOGGER.warning("Chroma retrieval failed. Switching to keyword fallback: %s", exc)
            matches = []

    if not matches:
        keyword_matches = search_manuals(query=query, manuals=MANUALS, top_k=top_k)
        matches = [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "tags": item.tags,
            }
            for item in keyword_matches
        ]

    return {
        "query": query,
        "matches": matches,
    }


if __name__ == "__main__":
    transport = os.getenv("RAG_SERVER_MCP_TRANSPORT", os.getenv("SENTINEL_MCP_TRANSPORT", "stdio"))
    if transport == "streamable-http":
        host = os.getenv("RAG_SERVER_MCP_HOST", os.getenv("SENTINEL_MCP_HOST", "127.0.0.1"))
        port = int(os.getenv("RAG_SERVER_MCP_PORT", os.getenv("SENTINEL_MCP_PORT", "8765")))
        path = os.getenv("RAG_SERVER_MCP_PATH", os.getenv("SENTINEL_MCP_PATH", "/mcp"))
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            path=path,
            show_banner=False,
        )
    else:
        mcp.run(transport="stdio", show_banner=False)
