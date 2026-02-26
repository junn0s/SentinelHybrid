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
RAG_CHUNK_ENABLED = os.getenv("RAG_CHUNK_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
RAG_CHUNK_SIZE_CHARS = max(200, int(os.getenv("RAG_CHUNK_SIZE_CHARS", "750")))
RAG_CHUNK_OVERLAP_CHARS = max(0, int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "120")))
RAG_CHUNK_QUERY_MULTIPLIER = max(1, int(os.getenv("RAG_CHUNK_QUERY_MULTIPLIER", "3")))


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


def _chunk_text(text: str) -> list[str]:
    normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = "\n".join(normalized_lines)
    if not normalized:
        return []
    if not RAG_CHUNK_ENABLED or len(normalized) <= RAG_CHUNK_SIZE_CHARS:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for line in normalized_lines:
        if not current:
            current = line
            continue
        candidate = f"{current}\n{line}"
        if len(candidate) <= RAG_CHUNK_SIZE_CHARS:
            current = candidate
            continue

        chunks.append(current)
        if RAG_CHUNK_OVERLAP_CHARS > 0 and len(current) > RAG_CHUNK_OVERLAP_CHARS:
            tail = current[-RAG_CHUNK_OVERLAP_CHARS :]
            if "\n" in tail:
                tail = tail.split("\n", 1)[1]
            current = f"{tail}\n{line}".strip()
        else:
            current = line

    if current:
        chunks.append(current)
    return chunks


def _build_index_records() -> tuple[list[str], list[str], list[dict]]:
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for manual in MANUALS:
        chunks = _chunk_text(manual.index_text())
        if not chunks:
            chunks = [manual.index_text()]
        total = len(chunks)

        for idx, chunk in enumerate(chunks, start=1):
            record_id = manual.id if not RAG_CHUNK_ENABLED else f"{manual.id}::chunk-{idx:02d}"
            ids.append(record_id)
            documents.append(_prepare_document_text(chunk))
            metadatas.append(
                {
                    "title": manual.title,
                    "tags": ",".join(manual.tags),
                    "hazard_type": manual.hazard_type,
                    "severity": manual.severity,
                    "version": manual.version,
                    "content": manual.content,
                    "parent_id": manual.id,
                    "chunk_index": idx,
                    "chunk_total": total,
                }
            )

    return ids, documents, metadatas


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

        ids, documents, metadatas = _build_index_records()

        # Keep manual entries synchronized and remove stale IDs.
        try:
            existing_ids = set(collection.get(include=[])["ids"])
            stale_ids = list(existing_ids.difference(ids))
            if stale_ids:
                collection.delete(ids=stale_ids)
        except Exception as exc:
            LOGGER.warning("Could not prune stale RAG records: %s", exc)

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

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
            n_results = top_k
            if RAG_CHUNK_ENABLED:
                n_results = max(top_k * RAG_CHUNK_QUERY_MULTIPLIER, top_k)

            result = CHROMA_COLLECTION.query(query_texts=[_prepare_query_text(query)], n_results=n_results)
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            seen_parents: set[str] = set()
            for idx, item_id in enumerate(ids):
                meta = metas[idx] if idx < len(metas) else {}
                tags = []
                if isinstance(meta, dict) and isinstance(meta.get("tags"), str):
                    tags = [t for t in meta["tags"].split(",") if t]
                parent_id = str(meta.get("parent_id", item_id)) if isinstance(meta, dict) else str(item_id)
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                content = _cleanup_document_text(str(docs[idx])) if idx < len(docs) else ""
                if isinstance(meta, dict) and isinstance(meta.get("content"), str) and meta.get("content", "").strip():
                    content = str(meta["content"]).strip()
                matches.append(
                    {
                        "id": parent_id,
                        "title": str(meta.get("title", "RAG Match")) if isinstance(meta, dict) else "RAG Match",
                        "content": content,
                        "tags": tags,
                    }
                )
                if len(matches) >= top_k:
                    break
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
