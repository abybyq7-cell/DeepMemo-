from ai_tutor import LearningEngine


def _engine_stub() -> LearningEngine:
    engine = object.__new__(LearningEngine)
    engine.model_reasoner = "deepseek-reasoner"
    engine.model_chat = "deepseek-chat"
    return engine


def _collect_keys(node):
    keys = []
    if isinstance(node, dict):
        for k, v in node.items():
            keys.append(str(k))
            keys.extend(_collect_keys(v))
    elif isinstance(node, list):
        for item in node:
            keys.extend(_collect_keys(item))
    return keys


def test_normalize_topic_input_returns_expected_fields():
    engine = _engine_stub()

    def fake_safe_chat_json(**kwargs):
        return {
            "normalized_topic": "线性代数",
            "aliases": ["线代"],
            "confidence": 0.95,
            "needs_clarification": False,
            "clarification_question": "",
        }

    engine._safe_chat_json = fake_safe_chat_json  # type: ignore[attr-defined]
    result = engine.normalize_topic_input("线代")

    assert result["normalized_topic"] == "线性代数"
    assert isinstance(result["aliases"], list)
    assert "confidence" in result
    assert "language" in result
    assert "assumptions" in result


def test_classify_topic_type_supports_knowledge_point_and_subject():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    subject = engine.classify_topic_type("线性代数")
    point = engine.classify_topic_type("TCP 三次握手")

    assert subject["topic_type"] == "subject"
    assert point["topic_type"] == "knowledge_point"


def test_infer_topic_scope_returns_domain_and_prerequisites():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    result = engine.infer_topic_scope("线性代数", "subject", language="zh-CN")

    assert result["domain"]
    assert isinstance(result["prerequisites"], list)
    assert len(result["prerequisites"]) > 0


def test_build_learning_framework_returns_structures_by_topic_type():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    scope_subject = engine.infer_topic_scope("线性代数", "subject", language="zh-CN")
    fw_subject = engine.build_learning_framework("线性代数", "subject", scope_subject, language="zh-CN")

    scope_point = engine.infer_topic_scope("TCP 三次握手", "knowledge_point", language="zh-CN")
    fw_point = engine.build_learning_framework("TCP 三次握手", "knowledge_point", scope_point, language="zh-CN")

    assert fw_subject["style"] == "textbook"
    assert "chapters" in fw_subject and isinstance(fw_subject["chapters"], list)

    assert fw_point["style"] == "micro_curriculum"
    assert "modules" in fw_point and isinstance(fw_point["modules"], list)


def test_plan_learning_path_fallback_when_model_returns_invalid_json_is_stable():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    result = engine.plan_learning_path("高数极限")

    assert result["normalized_topic"]
    assert isinstance(result["path"], list)
    assert len(result["path"]) > 0
    assert isinstance(result["framework"], dict)
    assert result["topic_type"] in {"knowledge_point", "subject", "mixed", "invalid"}
    expected_keys = {
        "normalized_topic",
        "topic_type",
        "domain",
        "subject_family",
        "aliases",
        "confidence",
        "needs_clarification",
        "clarification_question",
        "prerequisites",
        "framework",
        "path",
        "assumptions",
    }
    assert set(result.keys()) == expected_keys


def test_plan_learning_path_keeps_backward_compatible_fields():
    engine = _engine_stub()
    engine._safe_chat_json = lambda **kwargs: None  # type: ignore[attr-defined]

    result = engine.plan_learning_path("tcp三次握手")

    assert "normalized_topic" in result
    assert "path" in result
    assert "assumptions" in result
    assert isinstance(result["path"], list)


def test_plan_learning_path_rejects_explanatory_keys():
    engine = _engine_stub()

    def fake_safe_chat_json(**kwargs):
        system_prompt = str(kwargs.get("system_prompt", ""))
        if "Framework Builder" in system_prompt:
            return {
                "style": "micro_curriculum",
                "Definition": "bad",
                "modules": [{"title": "A", "goal": "B"}],
            }
        return None

    engine._safe_chat_json = fake_safe_chat_json  # type: ignore[attr-defined]
    result = engine.plan_learning_path("TCP 三次握手")

    all_keys = {k.lower() for k in _collect_keys(result["framework"])}
    assert "definition" not in all_keys
    assert "key idea" not in all_keys
    assert "practical example" not in all_keys


def test_plan_learning_path_downgrades_mixed_topic_to_knowledge_point_framework():
    engine = _engine_stub()
    captured = {}

    def fake_safe_chat_json(**kwargs):
        system_prompt = str(kwargs.get("system_prompt", ""))
        if "Topic Normalizer" in system_prompt:
            return {
                "normalized_topic": "线性代数与高等数学",
                "aliases": ["线代和高数"],
                "confidence": 0.81,
                "needs_clarification": False,
                "clarification_question": "",
            }
        if "Topic Classifier" in system_prompt:
            return {
                "topic_type": "mixed",
                "confidence": 0.66,
                "needs_clarification": True,
                "clarification_question": "请先确定一个主主题。",
            }
        if "Framework Builder" in system_prompt:
            captured["user_prompt"] = str(kwargs.get("user_prompt", ""))
            return {
                "style": "micro_curriculum",
                "modules": [
                    {"title": "概念定义", "goal": "明确范围"},
                    {"title": "直觉理解", "goal": "建立直觉"},
                    {"title": "前置知识", "goal": "补齐基础"},
                    {"title": "核心机制", "goal": "理解机制"},
                    {"title": "例题或应用", "goal": "迁移到题目"},
                    {"title": "常见错误", "goal": "规避误区"},
                ],
            }
        return None

    engine._safe_chat_json = fake_safe_chat_json  # type: ignore[attr-defined]
    result = engine.plan_learning_path("线代和高数")

    assert result["topic_type"] == "mixed"
    assert result["framework"]["style"] == "micro_curriculum"
    assert "Topic type: knowledge_point" in captured["user_prompt"]
