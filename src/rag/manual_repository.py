import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManualEntry:
    id: str
    title: str
    tags: list[str]
    content: str
    hazard_type: str = "general"
    severity: str = "medium"
    situation: str = ""
    immediate_actions: list[str] | None = None
    secondary_actions: list[str] | None = None
    reporting: list[str] | None = None
    ppe: list[str] | None = None
    prohibitions: list[str] | None = None
    restart_conditions: list[str] | None = None
    trigger_signals: list[str] | None = None
    first_60_sec: list[str] | None = None
    first_5_min: list[str] | None = None
    escalation_criteria: list[str] | None = None
    version: str = "1.0"
    updated_at: str = ""
    source: str = ""

    def index_text(self) -> str:
        blocks: list[str] = []
        blocks.append(f"[제목] {self.title}")
        blocks.append(f"[위험유형] {self.hazard_type}")
        blocks.append(f"[심각도] {self.severity}")
        if self.situation:
            blocks.append(f"[상황] {self.situation}")
        if self.immediate_actions:
            blocks.append("[즉시조치] " + " / ".join(self.immediate_actions))
        if self.secondary_actions:
            blocks.append("[후속조치] " + " / ".join(self.secondary_actions))
        if self.reporting:
            blocks.append("[보고체계] " + " / ".join(self.reporting))
        if self.ppe:
            blocks.append("[보호구] " + " / ".join(self.ppe))
        if self.prohibitions:
            blocks.append("[금지사항] " + " / ".join(self.prohibitions))
        if self.restart_conditions:
            blocks.append("[재개조건] " + " / ".join(self.restart_conditions))
        if self.trigger_signals:
            blocks.append("[트리거신호] " + " / ".join(self.trigger_signals))
        if self.first_60_sec:
            blocks.append("[60초조치] " + " / ".join(self.first_60_sec))
        if self.first_5_min:
            blocks.append("[5분조치] " + " / ".join(self.first_5_min))
        if self.escalation_criteria:
            blocks.append("[상향조건] " + " / ".join(self.escalation_criteria))
        if self.tags:
            blocks.append("[태그] " + ", ".join(self.tags))
        if self.content:
            blocks.append("[요약] " + self.content)
        return "\n".join(blocks)


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"\W+", text.lower()) if tok}


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _compose_content_from_fields(raw: dict) -> str:
    situation = str(raw.get("situation", "")).strip()
    immediate = _as_str_list(raw.get("immediate_actions"))
    secondary = _as_str_list(raw.get("secondary_actions"))
    reporting = _as_str_list(raw.get("reporting"))
    prohibitions = _as_str_list(raw.get("prohibitions"))
    restart = _as_str_list(raw.get("restart_conditions"))
    trigger = _as_str_list(raw.get("trigger_signals"))
    first_60 = _as_str_list(raw.get("first_60_sec"))
    first_5 = _as_str_list(raw.get("first_5_min"))
    escalation = _as_str_list(raw.get("escalation_criteria"))

    parts: list[str] = []
    if situation:
        parts.append(f"상황: {situation}")
    if immediate:
        parts.append("즉시조치: " + "; ".join(immediate))
    if secondary:
        parts.append("후속조치: " + "; ".join(secondary))
    if reporting:
        parts.append("보고체계: " + "; ".join(reporting))
    if prohibitions:
        parts.append("금지사항: " + "; ".join(prohibitions))
    if restart:
        parts.append("재개조건: " + "; ".join(restart))
    if trigger:
        parts.append("트리거신호: " + "; ".join(trigger))
    if first_60:
        parts.append("60초조치: " + "; ".join(first_60))
    if first_5:
        parts.append("5분조치: " + "; ".join(first_5))
    if escalation:
        parts.append("상향조건: " + "; ".join(escalation))
    return " ".join(parts).strip()


def load_manuals(manual_path: Path | None = None) -> list[ManualEntry]:
    path = manual_path or Path(__file__).with_name("default_manuals.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    manuals: list[ManualEntry] = []
    for item in raw:
        content = str(item.get("content", "")).strip() or _compose_content_from_fields(item)
        manuals.append(
            ManualEntry(
                id=item["id"],
                title=item["title"],
                tags=list(item.get("tags", [])),
                content=content,
                hazard_type=str(item.get("hazard_type", "general")).strip().lower() or "general",
                severity=str(item.get("severity", "medium")).strip().lower() or "medium",
                situation=str(item.get("situation", "")).strip(),
                immediate_actions=_as_str_list(item.get("immediate_actions")),
                secondary_actions=_as_str_list(item.get("secondary_actions")),
                reporting=_as_str_list(item.get("reporting")),
                ppe=_as_str_list(item.get("ppe")),
                prohibitions=_as_str_list(item.get("prohibitions")),
                restart_conditions=_as_str_list(item.get("restart_conditions")),
                trigger_signals=_as_str_list(item.get("trigger_signals")),
                first_60_sec=_as_str_list(item.get("first_60_sec")),
                first_5_min=_as_str_list(item.get("first_5_min")),
                escalation_criteria=_as_str_list(item.get("escalation_criteria")),
                version=str(item.get("version", "1.0")).strip() or "1.0",
                updated_at=str(item.get("updated_at", "")).strip(),
                source=str(item.get("source", "")).strip(),
            )
        )
    return manuals


def search_manuals(query: str, manuals: list[ManualEntry], top_k: int = 3) -> list[ManualEntry]:
    q_tokens = _tokenize(query)
    scored: list[tuple[int, ManualEntry]] = []

    for entry in manuals:
        title_tokens = _tokenize(entry.title)
        tag_tokens = _tokenize(" ".join(entry.tags))
        hazard_tokens = _tokenize(entry.hazard_type)
        situation_tokens = _tokenize(entry.situation)
        action_tokens = _tokenize(
            " ".join(
                [
                    *(entry.immediate_actions or []),
                    *(entry.secondary_actions or []),
                    *(entry.reporting or []),
                    *(entry.prohibitions or []),
                    *(entry.restart_conditions or []),
                    *(entry.trigger_signals or []),
                    *(entry.first_60_sec or []),
                    *(entry.first_5_min or []),
                    *(entry.escalation_criteria or []),
                ]
            )
        )
        content_tokens = _tokenize(entry.content)

        score = 0
        score += 3 * len(q_tokens.intersection(title_tokens))
        score += 3 * len(q_tokens.intersection(tag_tokens))
        score += 3 * len(q_tokens.intersection(hazard_tokens))
        score += 2 * len(q_tokens.intersection(situation_tokens))
        score += 2 * len(q_tokens.intersection(action_tokens))
        score += 1 * len(q_tokens.intersection(content_tokens))
        if score > 0:
            scored.append((score, entry))

    if not scored:
        # Always return at least one fallback guideline.
        return manuals[:1]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]
