from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .base import detect_language, load_prompt, safe_confidence


class TopicClassifierModule:
    VERSION = "1.0.0"
    INPUT_SCHEMA = {
        "normalized_topic": "str",
        "user_input": "str",
        "language": "Optional[str]",
    }
    OUTPUT_SCHEMA = {
        "topic_type": "knowledge_point|subject|mixed|invalid",
        "confidence": "float(0-1)",
        "needs_clarification": "bool",
        "clarification_question": "str",
        "assumptions": "List[str]",
        "source": "model|fallback",
        "version": "str",
    }

    def __init__(self, chat_json: Callable[..., Optional[Any]], model_reasoner: str) -> None:
        self._chat_json = chat_json
        self._model_reasoner = model_reasoner
        self._prompt_path = Path(__file__).resolve().parent / "prompts" / "topic_classifier.prompt.md"

    @staticmethod
    def _is_valid_payload(payload: Dict[str, Any]) -> bool:
        required = {"topic_type", "confidence", "needs_clarification", "clarification_question"}
        return required.issubset(payload.keys())

    @staticmethod
    def _fallback_topic_type(topic: str) -> str:
        t = (topic or "").strip().lower()
        subject_terms = {
            "线性代数", "高等数学", "概率论", "离散数学", "数学",
            "数据结构", "操作系统", "计算机网络", "编译原理", "数据库",
            "linear algebra", "calculus", "probability", "machine learning",
            "operating systems", "computer networks", "database systems",
        }
        knowledge_markers = ["中的", "握手", "定理", "算法", "机制", "原理", "极限", "limit", "handshake", "algorithm", "theorem"]
        if t in subject_terms or t.endswith("学") or t.endswith("导论"):
            return "subject"
        if any(k in t for k in knowledge_markers):
            return "knowledge_point"
        return "knowledge_point"

    def _fallback(self, normalized_topic: str, user_input: str = "", language: Optional[str] = None) -> Dict[str, Any]:
        topic = (normalized_topic or user_input or "").strip()
        lang = detect_language(topic, language)
        if not topic:
            return {
                "topic_type": "invalid",
                "confidence": 0.4,
                "needs_clarification": True,
                "clarification_question": "请提供更具体的主题，例如“线性代数”或“TCP 三次握手”。" if lang == "zh-CN" else "Please provide a more specific topic, such as 'Linear Algebra' or 'TCP three-way handshake'.",
                "assumptions": ["Empty topic treated as invalid in fallback."],
                "source": "fallback",
                "version": self.VERSION,
            }
        topic_lower = topic.lower()
        if any(x in topic_lower for x in [" and ", "/", "与", "、"]):
            return {
                "topic_type": "mixed",
                "confidence": 0.55,
                "needs_clarification": True,
                "clarification_question": "这个输入包含多个主题，请先确定一个主主题。" if lang == "zh-CN" else "This input contains multiple topics. Please choose one primary topic first.",
                "assumptions": ["Multiple-topic marker detected in deterministic fallback."],
                "source": "fallback",
                "version": self.VERSION,
            }
        return {
            "topic_type": self._fallback_topic_type(topic),
            "confidence": 0.65,
            "needs_clarification": False,
            "clarification_question": "",
            "assumptions": ["Deterministic classification fallback used."],
            "source": "fallback",
            "version": self.VERSION,
        }

    def run(self, normalized_topic: str, user_input: str = "", language: Optional[str] = None) -> Dict[str, Any]:
        fallback = self._fallback(normalized_topic=normalized_topic, user_input=user_input, language=language)
        prompt = load_prompt(
            self._prompt_path,
            "You classify learner topic granularity. Return JSON only.",
        )
        user_prompt = f"Normalized topic: {normalized_topic}\nOriginal input: {user_input}"
        parsed = self._chat_json(
            model=self._model_reasoner,
            system_prompt=prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=500,
        )
        if not isinstance(parsed, dict) or not self._is_valid_payload(parsed):
            return fallback

        topic_type = str(parsed.get("topic_type", fallback["topic_type"])).strip().lower()
        if topic_type not in {"subject", "knowledge_point", "mixed", "invalid"}:
            topic_type = fallback["topic_type"]
        return {
            "topic_type": topic_type,
            "confidence": safe_confidence(parsed.get("confidence", fallback["confidence"]), fallback["confidence"]),
            "needs_clarification": bool(parsed.get("needs_clarification", fallback["needs_clarification"])),
            "clarification_question": str(parsed.get("clarification_question", fallback["clarification_question"])).strip(),
            "assumptions": ["Model-based classification used."],
            "source": "model",
            "version": self.VERSION,
        }
