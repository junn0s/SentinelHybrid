from src.rag.manual_repository import load_manuals, search_manuals

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("fastmcp is required to run the MCP RAG server.") from exc

mcp = FastMCP("SentinelHybridRAG")
MANUALS = load_manuals()
CHROMA_COLLECTION = None


def _init_chroma() -> None:
    global CHROMA_COLLECTION
    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path="data/chroma")
        collection = client.get_or_create_collection(name="sentinelhybrid_manuals")

        # Seed collection once.
        existing = collection.count()
        if existing == 0:
            collection.add(
                ids=[m.id for m in MANUALS],
                documents=[m.content for m in MANUALS],
                metadatas=[{"title": m.title, "tags": ",".join(m.tags)} for m in MANUALS],
            )

        CHROMA_COLLECTION = collection
    except Exception:
        CHROMA_COLLECTION = None


_init_chroma()


@mcp.tool
def retrieve_guidelines(query: str, top_k: int = 3) -> dict:
    matches = []
    if CHROMA_COLLECTION is not None:
        try:
            result = CHROMA_COLLECTION.query(query_texts=[query], n_results=top_k)
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
                        "content": str(docs[idx]) if idx < len(docs) else "",
                        "tags": tags,
                    }
                )
        except Exception:
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
    mcp.run()
