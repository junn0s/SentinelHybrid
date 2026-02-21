from src.api.services.mcp_base import normalize_mcp_result


def test_normalize_mcp_result_json_text_block() -> None:
    raw = [{"type": "text", "text": "{\"status\":\"ok\",\"value\":1}"}]
    normalized = normalize_mcp_result(raw)
    assert isinstance(normalized, dict)
    assert normalized["status"] == "ok"
    assert normalized["value"] == 1


def test_normalize_mcp_result_plain_text_block() -> None:
    raw = [{"type": "text", "text": "plain-text"}]
    normalized = normalize_mcp_result(raw)
    assert normalized == "plain-text"


def test_normalize_mcp_result_json_string() -> None:
    raw = "{\"matches\":[{\"id\":\"a\"}]}"
    normalized = normalize_mcp_result(raw)
    assert isinstance(normalized, dict)
    assert isinstance(normalized.get("matches"), list)
