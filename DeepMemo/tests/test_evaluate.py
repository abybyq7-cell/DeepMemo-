from ai_tutor import parse_llm_json


def test_parse_llm_json_plain_json():
    result = parse_llm_json('{"is_correct": true, "content": "ok"}')
    assert result == {"is_correct": True, "content": "ok"}


def test_parse_llm_json_markdown_block():
    payload = """```json
{"is_correct": false, "content": "bad"}
```"""
    result = parse_llm_json(payload)
    assert result == {"is_correct": False, "content": "bad"}
