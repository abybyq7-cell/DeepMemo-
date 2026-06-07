from ai_tutor import LearningEngine

from memory.learning_path import LearningPathMemoryStore


def _engine_stub() -> LearningEngine:
    engine = object.__new__(LearningEngine)
    engine.model_reasoner = "deepseek-reasoner"
    engine.model_chat = "deepseek-chat"
    return engine


def test_orchestrator_fallback_stable_when_all_module_calls_fail():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    result = engine.plan_learning_path("高数极限")

    assert result["normalized_topic"]
    assert isinstance(result["path"], list) and len(result["path"]) > 0
    assert isinstance(result["framework"], dict)
    assert "assumptions" in result and isinstance(result["assumptions"], list)
    assert result["topic_type"] in {"knowledge_point", "subject", "mixed", "invalid"}


def test_orchestrator_reuses_topic_memory_for_scope_and_framework(tmp_path):
    engine = _engine_stub()
    engine._learning_path_memory_store = LearningPathMemoryStore(tmp_path / "learning_path_memory.json")  # type: ignore[attr-defined]
    calls = {"normalize": 0, "classify": 0, "scope": 0, "framework": 0}

    def fake_safe_chat_json(**kwargs):
        system_prompt = str(kwargs.get("system_prompt", ""))
        if "Topic Normalizer" in system_prompt:
            calls["normalize"] += 1
            return {
                "normalized_topic": "线性代数",
                "aliases": ["线代"],
                "confidence": 0.92,
                "needs_clarification": False,
                "clarification_question": "",
            }
        if "Topic Classifier" in system_prompt:
            calls["classify"] += 1
            return {
                "topic_type": "subject",
                "confidence": 0.88,
                "needs_clarification": False,
                "clarification_question": "",
            }
        if "Scope Inference" in system_prompt:
            calls["scope"] += 1
            return {
                "domain": "数学",
                "subject_family": "高等数学",
                "prerequisites": ["代数基础", "函数与图像"],
            }
        if "Framework Builder" in system_prompt:
            calls["framework"] += 1
            return {
                "style": "textbook",
                "chapters": [
                    {"title": "基础概念与记号", "sections": ["学科范围", "核心术语"]},
                    {"title": "基本理论与结构", "sections": ["基本法则", "关键命题"]},
                    {"title": "标准方法与解题流程", "sections": ["常用方法", "典型题型"]},
                    {"title": "应用场景与综合训练", "sections": ["基础应用", "综合案例"]},
                ],
            }
        return None

    engine._safe_chat_json = fake_safe_chat_json  # type: ignore[attr-defined]

    first = engine.plan_learning_path("线代")
    second = engine.plan_learning_path("线代")

    assert first["normalized_topic"] == "线性代数"
    assert second["normalized_topic"] == "线性代数"
    assert first["path"] == second["path"]
    assert calls["normalize"] == 2
    assert calls["classify"] == 2
    assert calls["scope"] == 1
    assert calls["framework"] == 1
    trace = engine.get_last_learning_path_trace()
    assert any(item["stage"] == "memory" for item in trace)

