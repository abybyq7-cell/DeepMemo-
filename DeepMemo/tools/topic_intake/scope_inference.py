from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .base import detect_language, load_prompt


class ScopeInferenceModule:
    VERSION = "1.0.0"
    INPUT_SCHEMA = {
        "normalized_topic": "str",
        "topic_type": "knowledge_point|subject|mixed|invalid",
        "language": "Optional[str]",
    }
    OUTPUT_SCHEMA = {
        "domain": "str",
        "subject_family": "str",
        "prerequisites": "List[str]",
        "assumptions": "List[str]",
        "source": "model|fallback|memory",
        "version": "str",
    }

    def __init__(self, chat_json: Callable[..., Optional[Any]], model_reasoner: str) -> None:
        self._chat_json = chat_json
        self._model_reasoner = model_reasoner
        self._prompt_path = Path(__file__).resolve().parent / "prompts" / "scope_inference.prompt.md"

    @staticmethod
    def _is_valid_payload(payload: Dict[str, Any]) -> bool:
        required = {"domain", "subject_family", "prerequisites"}
        return required.issubset(payload.keys())

    def _fallback(self, normalized_topic: str, topic_type: str, language: Optional[str] = None) -> Dict[str, Any]:
        topic = (normalized_topic or "").lower()
        lang = detect_language(normalized_topic, language)
        zh = lang == "zh-CN"

        if any(k in topic for k in ["代数", "数学", "calculus", "algebra", "probability"]):
            domain = "数学" if zh else "Mathematics"
            family = "高等数学" if zh else "Higher Mathematics"
            prereq = (["代数基础", "函数与图像"] if zh else ["Basic algebra", "Functions and graphs"]) if topic_type == "subject" else (["函数概念", "基本极限"] if zh else ["Function concept", "Basic limits"])
        elif any(k in topic for k in ["tcp", "network", "网络", "协议"]):
            domain = "计算机科学" if zh else "Computer Science"
            family = "计算机网络" if zh else "Computer Networks"
            prereq = ["二进制与数据表示", "OSI/TCP-IP 分层基础"] if zh else ["Binary and data representation", "OSI/TCP-IP basic layers"]
        else:
            domain = "综合领域" if zh else "General Domain"
            family = "通用学科" if zh else "General"
            prereq = ["基础数学", "逻辑推理"] if zh else ["Basic high-school math", "Logical reasoning"]

        return {
            "domain": domain,
            "subject_family": family,
            "prerequisites": prereq,
            "assumptions": ["Deterministic scope fallback used."],
            "source": "fallback",
            "version": self.VERSION,
        }

    def run(self, normalized_topic: str, topic_type: str, language: Optional[str] = None) -> Dict[str, Any]:
        fallback = self._fallback(normalized_topic=normalized_topic, topic_type=topic_type, language=language)
        prompt = load_prompt(
            self._prompt_path,
            "You infer scope information for a learner topic. Return JSON only.",
        )
        user_prompt = f"Topic: {normalized_topic}\nTopic type: {topic_type}"
        parsed = self._chat_json(
            model=self._model_reasoner,
            system_prompt=prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=800,
        )
        if not isinstance(parsed, dict) or not self._is_valid_payload(parsed):
            return fallback

        domain = str(parsed.get("domain", fallback["domain"])).strip() or fallback["domain"]
        subject_family = str(parsed.get("subject_family", fallback["subject_family"])).strip() or fallback["subject_family"]
        prerequisites = parsed.get("prerequisites", fallback["prerequisites"])
        prerequisites = [str(x).strip() for x in prerequisites if str(x).strip()] if isinstance(prerequisites, list) else fallback["prerequisites"]
        return {
            "domain": domain,
            "subject_family": subject_family,
            "prerequisites": prerequisites,
            "assumptions": ["Model-based scope inference used."],
            "source": "model",
            "version": self.VERSION,
        }
