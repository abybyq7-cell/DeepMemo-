from tools.topic_intake.framework_builder import FrameworkBuilderModule
from tools.topic_intake.scope_inference import ScopeInferenceModule
from tools.topic_intake.topic_classifier import TopicClassifierModule
from tools.topic_intake.topic_normalizer import TopicNormalizerModule


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


def test_topic_normalizer_module_fields_and_version():
    module = TopicNormalizerModule(chat_json=lambda **kwargs: None, model_reasoner="m")
    result = module.run("线代")

    assert result["normalized_topic"]
    assert isinstance(result["aliases"], list)
    assert isinstance(result["confidence"], float)
    assert result["version"] == module.VERSION


def test_topic_classifier_module_distinguishes_subject_and_knowledge_point():
    module = TopicClassifierModule(chat_json=lambda **kwargs: None, model_reasoner="m")

    subject = module.run(normalized_topic="线性代数")
    point = module.run(normalized_topic="TCP 三次握手")

    assert subject["topic_type"] == "subject"
    assert point["topic_type"] == "knowledge_point"
    assert subject["version"] == module.VERSION


def test_scope_inference_module_returns_domain_and_prerequisites():
    module = ScopeInferenceModule(chat_json=lambda **kwargs: None, model_reasoner="m")
    result = module.run(normalized_topic="线性代数", topic_type="subject", language="zh-CN")

    assert result["domain"]
    assert isinstance(result["prerequisites"], list)
    assert len(result["prerequisites"]) > 0
    assert result["version"] == module.VERSION


def test_framework_builder_module_returns_two_styles():
    module = FrameworkBuilderModule(chat_json=lambda **kwargs: None, model_reasoner="m")

    subject = module.run(
        normalized_topic="线性代数",
        topic_type="subject",
        scope_info={"domain": "数学", "subject_family": "高等数学", "prerequisites": ["代数基础"]},
        language="zh-CN",
    )
    point = module.run(
        normalized_topic="TCP 三次握手",
        topic_type="knowledge_point",
        scope_info={"domain": "计算机科学", "subject_family": "计算机网络", "prerequisites": ["OSI"]},
        language="zh-CN",
    )

    assert subject["framework"]["style"] == "textbook"
    assert "chapters" in subject["framework"]
    assert point["framework"]["style"] == "micro_curriculum"
    assert "modules" in point["framework"]
    assert subject["version"] == module.VERSION
    assert point["version"] == module.VERSION


def test_framework_builder_rejects_explanatory_keys_and_falls_back():
    def fake_chat_json(**kwargs):
        return {
            "style": "micro_curriculum",
            "Definition": "bad",
            "modules": [{"title": "A", "goal": "B"}],
        }

    module = FrameworkBuilderModule(chat_json=fake_chat_json, model_reasoner="m")
    result = module.run(
        normalized_topic="TCP 三次握手",
        topic_type="knowledge_point",
        scope_info={"domain": "计算机科学", "subject_family": "计算机网络", "prerequisites": ["OSI"]},
        language="zh-CN",
    )

    all_keys = {k.lower() for k in _collect_keys(result["framework"])}
    assert "definition" not in all_keys
    assert "key idea" not in all_keys
    assert "practical example" not in all_keys

