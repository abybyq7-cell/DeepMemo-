from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .base import canonicalize_topic_text, detect_language, load_prompt, safe_confidence


class TopicNormalizerModule:
    VERSION = "1.0.0"
    INPUT_SCHEMA = {
        "user_input": "str",
        "language": "Optional[str]",
    }
    OUTPUT_SCHEMA = {
        "normalized_topic": "str",
        "aliases": "List[str]",
        "confidence": "float(0-1)",
        "needs_clarification": "bool",
        "clarification_question": "str",
        "language": "zh-CN|en",
        "assumptions": "List[str]",
        "source": "model|fallback",
        "version": "str",
    }

    def __init__(self, chat_json: Callable[..., Optional[Any]], model_reasoner: str) -> None:
        self._chat_json = chat_json
        self._model_reasoner = model_reasoner
        self._prompt_path = Path(__file__).resolve().parent / "prompts" / "topic_normalizer.prompt.md"

    @staticmethod
    def _is_valid_payload(payload: Dict[str, Any]) -> bool:
        required = {"normalized_topic", "aliases", "confidence", "needs_clarification", "clarification_question"}
        return required.issubset(payload.keys())

    def _fallback(self, user_input: str, language: Optional[str] = None) -> Dict[str, Any]:
        lang = detect_language(user_input, language)
        canonical = canonicalize_topic_text(user_input)
        topic = canonical or ("未命名主题" if lang == "zh-CN" else "Untitled Topic")
        aliases = []
        raw = (user_input or "").strip()
        if raw and raw != topic:
            aliases.append(raw)
        return {
            "normalized_topic": topic,
            "aliases": aliases,
            "confidence": 0.68,
            "needs_clarification": False,
            "clarification_question": "",
            "language": lang,
            "assumptions": ["Deterministic normalization fallback used."],
            "source": "fallback",
            "version": self.VERSION,
        }

    def run(self, user_input: str, language: Optional[str] = None) -> Dict[str, Any]:
        fallback = self._fallback(user_input=user_input, language=language)
        output_lang = "Chinese (Simplified)" if fallback["language"] == "zh-CN" else "English"
        prompt = load_prompt(
            self._prompt_path,
            "You normalize learner topic input. Return JSON only.",
        )
        user_prompt = (
            f"Input topic: {user_input}\n"
            f"Canonical hint: {canonicalize_topic_text(user_input)}\n"
            f"Output language for labels: {output_lang}"
        )
        parsed = self._chat_json(
            model=self._model_reasoner,
            system_prompt=prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=700,
        )
        if not isinstance(parsed, dict) or not self._is_valid_payload(parsed):
            return fallback

        normalized_topic = str(parsed.get("normalized_topic", fallback["normalized_topic"])).strip() or fallback["normalized_topic"]
        aliases = parsed.get("aliases", fallback["aliases"])
        aliases = [str(x).strip() for x in aliases if str(x).strip()] if isinstance(aliases, list) else fallback["aliases"]
        return {
            "normalized_topic": normalized_topic,
            "aliases": aliases,
            "confidence": safe_confidence(parsed.get("confidence", fallback["confidence"]), fallback["confidence"]),
            "needs_clarification": bool(parsed.get("needs_clarification", fallback["needs_clarification"])),
            "clarification_question": str(parsed.get("clarification_question", fallback["clarification_question"])).strip(),
            "language": fallback["language"],
            "assumptions": ["Model-based normalization used."],
            "source": "model",
            "version": self.VERSION,
        }
