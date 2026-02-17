import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManualEntry:
    id: str
    title: str
    content: str
    tags: list[str]


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"\W+", text.lower()) if tok}


def load_manuals(manual_path: Path | None = None) -> list[ManualEntry]:
    path = manual_path or Path(__file__).with_name("default_manuals.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    manuals: list[ManualEntry] = []
    for item in raw:
        manuals.append(
            ManualEntry(
                id=item["id"],
                title=item["title"],
                content=item["content"],
                tags=list(item.get("tags", [])),
            )
        )
    return manuals


def search_manuals(query: str, manuals: list[ManualEntry], top_k: int = 3) -> list[ManualEntry]:
    q_tokens = _tokenize(query)
    scored: list[tuple[int, ManualEntry]] = []

    for entry in manuals:
        entry_tokens = _tokenize(" ".join([entry.title, entry.content, *entry.tags]))
        score = len(q_tokens.intersection(entry_tokens))
        if score > 0:
            scored.append((score, entry))

    if not scored:
        # Always return at least one fallback guideline.
        return manuals[:1]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]

