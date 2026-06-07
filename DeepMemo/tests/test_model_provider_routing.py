import pytest

from ai_tutor import LearningEngine, _engine_kwargs_from_user_context
from tools.utils import api_client


def test_engine_kwargs_from_user_context_for_kimi():
    kwargs = _engine_kwargs_from_user_context(
        {
            "ai_provider": "kimi",
            "ai_api_key": "sk-kimi-test",
            "ai_base_url": "",
            "ai_model_chat": "",
            "ai_model_reasoner": "",
        }
    )

    assert kwargs["api_key"] == "sk-kimi-test"
    assert kwargs["base_url"] == "https://api.moonshot.ai/v1"
    assert kwargs["model_chat"] == "kimi-k2-thinking-turbo"
    assert kwargs["model_reasoner"] == "kimi-k2-thinking"


def test_generate_explanation_posts_user_context(monkeypatch):
    captured = {}

    def fake_post(path, json, timeout=10.0):
        captured["path"] = path
        captured["json"] = json
        return {"explanation": "ok"}

    monkeypatch.setattr(api_client, "_post", fake_post)

    result = api_client.generate_explanation(
        "linear algebra",
        user_context={"ai_provider": "kimi", "ai_api_key": "sk-kimi-test"},
    )

    assert result == "ok"
    assert captured["path"] == "/explain"
    assert captured["json"]["topic"] == "linear algebra"
    assert captured["json"]["user_context"]["ai_provider"] == "kimi"


def test_chat_retries_with_temperature_one_on_provider_constraint():
    engine = object.__new__(LearningEngine)

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            if float(kwargs.get("temperature", 0.0)) != 1.0:
                raise Exception("invalid temperature: only 1 is supported")
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    engine._client = _Client()  # type: ignore[attr-defined]
    out = engine._chat(  # type: ignore[attr-defined]
        model="kimi-k2-thinking",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=16,
    )
    assert out == "ok"


def test_chat_does_not_retry_non_retryable_bad_request():
    engine = object.__new__(LearningEngine)
    calls = {"count": 0}

    class _BadRequestError(Exception):
        status_code = 400

    class _Completions:
        def create(self, **kwargs):
            calls["count"] += 1
            raise _BadRequestError("invalid api key")

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    engine._client = _Client()  # type: ignore[attr-defined]

    with pytest.raises(_BadRequestError):
        engine._chat(  # type: ignore[attr-defined]
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            max_tokens=16,
        )

    assert calls["count"] == 1
