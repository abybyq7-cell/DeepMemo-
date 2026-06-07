import json
import logging
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypedDict

import httpx
import openai
from openai import OpenAI

from memory.learning_path import LearningPathMemoryStore, LearningPathOrchestrator
from tools.topic_intake import (
    FrameworkBuilderModule,
    ScopeInferenceModule,
    TopicClassifierModule,
    TopicNormalizerModule,
)
from tools.utils import _encoding_fix  # noqa: F401
from tools.utils.config import API_KEY, BASE_URL, CACHE_FILE, MODEL_CHAT, MODEL_REASONER

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

class TopicNormalizeResult(TypedDict):
    normalized_topic: str
    aliases: List[str]
    confidence: float
    needs_clarification: bool
    clarification_question: str
    language: str
    assumptions: List[str]


class TopicClassifyResult(TypedDict):
    topic_type: str
    confidence: float
    needs_clarification: bool
    clarification_question: str
    assumptions: List[str]


class TopicScopeResult(TypedDict):
    domain: str
    subject_family: str
    prerequisites: List[str]
    assumptions: List[str]


class TopicAnalysisResult(TypedDict):
    normalized_topic: str
    topic_type: str
    domain: str
    subject_family: str
    aliases: List[str]
    confidence: float
    needs_clarification: bool
    clarification_question: str
    prerequisites: List[str]
    framework: Dict[str, Any]
    path: List[str]
    assumptions: List[str]



def parse_llm_json(text: str) -> Optional[Any]:
    """Best-effort parse for JSON returned by LLMs."""
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    think_match = re.search(r"<think>.*?</think>\s*(.*)", text, re.DOTALL)
    if think_match:
        text = think_match.group(1)

    code_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_match:
        text = code_match.group(1)

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        if "[" in text:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
    except Exception:
        pass

    return None


_RETRYABLE_STATUS_CODES = {408, 409, 425, 429}
_NON_RETRYABLE_MESSAGE_MARKERS = (
    "invalid api key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "permission",
    "not found",
    "unsupported",
    "invalid_request_error",
    "invalid parameter",
    "missing required parameter",
)
_RETRYABLE_MESSAGE_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection aborted",
    "connection refused",
    "temporary",
    "temporarily unavailable",
    "rate limit",
    "server error",
    "service unavailable",
)


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError, httpx.TransportError)):
        return True

    retryable_openai_errors = (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
    non_retryable_openai_errors = (
        openai.AuthenticationError,
        openai.BadRequestError,
        openai.PermissionDeniedError,
        openai.NotFoundError,
        openai.UnprocessableEntityError,
    )
    if isinstance(exc, non_retryable_openai_errors):
        return False
    if isinstance(exc, retryable_openai_errors):
        return True

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code in _RETRYABLE_STATUS_CODES or 500 <= status_code < 600:
            return True
        if 400 <= status_code < 500:
            return False

    message = str(exc).strip().lower()
    if any(marker in message for marker in _NON_RETRYABLE_MESSAGE_MARKERS):
        return False
    if any(marker in message for marker in _RETRYABLE_MESSAGE_MARKERS):
        return True
    return True


def _retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 2,
    base_delay: float = 1.0,
    *,
    operation: str = "operation",
    should_retry: Optional[Callable[[Exception], bool]] = None,
) -> Any:
    """Retry helper with exponential backoff."""
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:  # pragma: no cover
            last_exception = exc
            retryable = should_retry(exc) if should_retry else True
            error_name = type(exc).__name__
            error_message = str(exc).strip() or "<no error message>"

            if attempt < max_retries and retryable:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "%s failed on attempt %s/%s with %s: %s; retrying in %.1fs",
                    operation,
                    attempt + 1,
                    max_retries + 1,
                    error_name,
                    error_message,
                    delay,
                )
                time.sleep(delay)
            else:
                if retryable:
                    logger.error(
                        "%s failed after %s attempts with %s: %s",
                        operation,
                        max_retries + 1,
                        error_name,
                        error_message,
                    )
                else:
                    logger.error(
                        "%s failed with non-retryable %s: %s",
                        operation,
                        error_name,
                        error_message,
                    )
                raise

    raise last_exception  # type: ignore[misc]


class LearningEngine:
    """Stateless learning workflow engine backed by DeepSeek models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_chat: Optional[str] = None,
        model_reasoner: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or API_KEY
        self.base_url = base_url or BASE_URL
        self.model_chat = model_chat or MODEL_CHAT
        self.model_reasoner = model_reasoner or MODEL_REASONER

        if not self.api_key:
            raise RuntimeError("Missing API key: set DEEPSEEK_API_KEY or provide runtime ai_api_key")

        self._http_client = httpx.Client(
            timeout=60.0,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, http_client=self._http_client)

    def _chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
    ) -> str:
        def _call() -> str:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if timeout is not None:
                kwargs["timeout"] = timeout

            try:
                response = self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as exc:
                # Some providers/models only allow fixed temperature.
                # Retry once with temperature=1.0 to keep the call usable.
                msg = str(exc).lower()
                if "temperature" in msg and ("only 1" in msg or "invalid temperature" in msg):
                    kwargs["temperature"] = 1.0
                    response = self._client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content or ""
                raise

        return _retry_with_backoff(
            _call,
            max_retries=2,
            base_delay=1,
            operation=f"chat.completions.create[{model}]",
            should_retry=_is_retryable_error,
        )

    @staticmethod
    def _normalize_question(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        question = str(item.get("question", "")).strip()
        if not question:
            return None

        q_type = str(item.get("type", "open")).strip().lower()
        if q_type not in {"choice", "open"}:
            q_type = "open"

        options = item.get("options", []) if isinstance(item.get("options", []), list) else []
        options = [str(opt).strip() for opt in options if str(opt).strip()]

        if q_type == "choice" and len(options) < 2:
            q_type = "open"
            options = []

        hint = str(item.get("hint", "Focus on core principles.")).strip() or "Focus on core principles."

        return {
            "question": question,
            "type": q_type,
            "options": options,
            "hint": hint,
        }

    @staticmethod
    def _read_cache() -> List[Dict[str, Any]]:
        try:
            if CACHE_FILE.exists():
                with CACHE_FILE.open("r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, list):
                    return data
        except Exception as exc:
            logger.warning("Failed to read cache: %s", exc)
        return []

    @staticmethod
    def _write_cache(cache_data: List[Dict[str, Any]]) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w", encoding="utf-8") as fp:
            json.dump(cache_data, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _resolve_output_language(language: Optional[str]) -> str:
        """Map user language preference to output instruction."""
        lang = (language or "").strip().lower()
        if lang.startswith("zh"):
            return "Chinese (Simplified)"
        return "English"

    @staticmethod
    def _detect_input_language(user_input: str, language: Optional[str] = None) -> str:
        if language and str(language).strip():
            lang = str(language).strip().lower()
            return "zh-CN" if lang.startswith("zh") else "en"
        return "zh-CN" if re.search(r"[\u4e00-\u9fff]", user_input or "") else "en"

    @staticmethod
    def _canonicalize_topic_text(topic: str) -> str:
        raw = (topic or "").strip()
        lowered = raw.lower()
        alias_map = {
            "\u7ebf\u4ee3": "\u7ebf\u6027\u4ee3\u6570",
            "\u9ad8\u6570\u6781\u9650": "\u9ad8\u7b49\u6570\u5b66\u4e2d\u7684\u6781\u9650",
            "tcp\u4e09\u6b21\u63e1\u624b": "TCP \u4e09\u6b21\u63e1\u624b",
            "tcp 3\u6b21\u63e1\u624b": "TCP \u4e09\u6b21\u63e1\u624b",
            "tcp3\u6b21\u63e1\u624b": "TCP \u4e09\u6b21\u63e1\u624b",
        }
        return alias_map.get(lowered, raw)

    def _safe_chat_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Optional[Any]:
        try:
            raw = self._chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return parse_llm_json(raw)
        except Exception as exc:
            logger.warning("Model call failed: %s", exc)
            return None

    def _ensure_topic_intake_modules(self) -> None:
        if not hasattr(self, "_topic_normalizer"):
            self._topic_normalizer = TopicNormalizerModule(self._safe_chat_json, self.model_reasoner)  # type: ignore[attr-defined]
        if not hasattr(self, "_topic_classifier"):
            self._topic_classifier = TopicClassifierModule(self._safe_chat_json, self.model_reasoner)  # type: ignore[attr-defined]
        if not hasattr(self, "_scope_inference"):
            self._scope_inference = ScopeInferenceModule(self._safe_chat_json, self.model_reasoner)  # type: ignore[attr-defined]
        if not hasattr(self, "_framework_builder"):
            self._framework_builder = FrameworkBuilderModule(self._safe_chat_json, self.model_reasoner)  # type: ignore[attr-defined]

    def _ensure_learning_path_orchestrator(self) -> None:
        if hasattr(self, "_learning_path_orchestrator"):
            return

        memory_store = getattr(self, "_learning_path_memory_store", None)
        if not isinstance(memory_store, LearningPathMemoryStore):
            memory_file = getattr(self, "_learning_path_memory_file", None)
            memory_path = Path(memory_file) if memory_file else None
            memory_store = LearningPathMemoryStore(memory_file=memory_path)

        self._learning_path_orchestrator = LearningPathOrchestrator(  # type: ignore[attr-defined]
            chat_json=self._safe_chat_json,
            model_reasoner=self.model_reasoner,
            memory_store=memory_store,
        )

    @staticmethod
    def _fallback_topic_type(topic: str) -> str:
        t = (topic or "").strip().lower()
        subject_terms = {
            "\u7ebf\u6027\u4ee3\u6570", "\u9ad8\u7b49\u6570\u5b66", "\u6982\u7387\u8bba", "\u79bb\u6563\u6570\u5b66", "\u6570\u5b66",
            "\u6570\u636e\u7ed3\u6784", "\u64cd\u4f5c\u7cfb\u7edf", "\u8ba1\u7b97\u673a\u7f51\u7edc", "\u7f16\u8bd1\u539f\u7406", "\u6570\u636e\u5e93",
            "linear algebra", "calculus", "probability", "machine learning",
            "operating systems", "computer networks", "database systems",
        }
        knowledge_markers = [
            "\u4e2d\u7684", "\u63e1\u624b", "\u5b9a\u7406", "\u7b97\u6cd5", "\u673a\u5236", "\u539f\u7406", "\u6781\u9650",
            "limit", "handshake", "algorithm", "theorem",
        ]
        if t in subject_terms or t.endswith("\u5b66") or t.endswith("\u5bfc\u8bba"):
            return "subject"
        if any(k in t for k in knowledge_markers):
            return "knowledge_point"
        return "knowledge_point"

    @staticmethod
    def _safe_confidence(value: Any, default: float = 0.6) -> float:
        try:
            conf = float(value)
        except Exception:
            conf = default
        return max(0.0, min(1.0, conf))

    def _fallback_normalization(self, user_input: str, language: Optional[str] = None) -> TopicNormalizeResult:
        lang = self._detect_input_language(user_input, language)
        canonical = self._canonicalize_topic_text(user_input)
        topic = canonical or ("\u672a\u547d\u540d\u4e3b\u9898" if lang == "zh-CN" else "Untitled Topic")
        aliases: List[str] = []
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
        }

    def _fallback_classification(self, normalized_topic: str, user_input: str = "", language: Optional[str] = None) -> TopicClassifyResult:
        topic = (normalized_topic or user_input or "").strip()
        lang = self._detect_input_language(topic, language)
        if not topic:
            return {
                "topic_type": "invalid",
                "confidence": 0.4,
                "needs_clarification": True,
                "clarification_question": "\u8bf7\u63d0\u4f9b\u66f4\u5177\u4f53\u7684\u4e3b\u9898\uff0c\u4f8b\u5982\u201c\u7ebf\u6027\u4ee3\u6570\u201d\u6216\u201cTCP \u4e09\u6b21\u63e1\u624b\u201d\u3002" if lang == "zh-CN" else "Please provide a more specific topic, such as 'Linear Algebra' or 'TCP three-way handshake'.",
                "assumptions": ["Empty topic treated as invalid in fallback."],
            }
        topic_lower = topic.lower()
        if any(x in topic_lower for x in [" and ", "/", "\u4e0e", "\u3001"]):
            return {
                "topic_type": "mixed",
                "confidence": 0.55,
                "needs_clarification": True,
                "clarification_question": "\u8fd9\u4e2a\u8f93\u5165\u5305\u542b\u591a\u4e2a\u4e3b\u9898\uff0c\u8bf7\u5148\u786e\u5b9a\u4e00\u4e2a\u4e3b\u9898\u3002" if lang == "zh-CN" else "This input contains multiple topics. Please choose one primary topic first.",
                "assumptions": ["Multiple-topic marker detected in deterministic fallback."],
            }
        return {
            "topic_type": self._fallback_topic_type(topic),
            "confidence": 0.65,
            "needs_clarification": False,
            "clarification_question": "",
            "assumptions": ["Deterministic classification fallback used."],
        }

    def _fallback_scope(self, normalized_topic: str, topic_type: str, language: Optional[str] = None) -> TopicScopeResult:
        topic = normalized_topic.lower()
        lang = self._detect_input_language(normalized_topic, language)
        zh = lang == "zh-CN"
        if any(k in topic for k in ["\u4ee3\u6570", "\u6570\u5b66", "calculus", "algebra", "probability"]):
            domain = "\u6570\u5b66" if zh else "Mathematics"
            family = "\u9ad8\u7b49\u6570\u5b66" if zh else "Higher Mathematics"
            prereq = (["\u4ee3\u6570\u57fa\u7840", "\u51fd\u6570\u4e0e\u56fe\u50cf"] if zh else ["Basic algebra", "Functions and graphs"]) if topic_type == "subject" else (["\u51fd\u6570\u6982\u5ff5", "\u57fa\u672c\u6781\u9650"] if zh else ["Function concept", "Basic limits"])
        elif any(k in topic for k in ["tcp", "network", "\u7f51\u7edc", "\u534f\u8bae"]):
            domain = "\u8ba1\u7b97\u673a\u79d1\u5b66" if zh else "Computer Science"
            family = "\u8ba1\u7b97\u673a\u7f51\u7edc" if zh else "Computer Networks"
            prereq = ["\u4e8c\u8fdb\u5236\u4e0e\u6570\u636e\u8868\u793a", "OSI/TCP-IP \u5206\u5c42\u57fa\u7840"] if zh else ["Binary and data representation", "OSI/TCP-IP basic layers"]
        else:
            domain = "\u7efc\u5408\u9886\u57df" if zh else "General Domain"
            family = "\u901a\u7528\u5b66\u79d1" if zh else "General"
            prereq = ["\u57fa\u7840\u6570\u5b66", "\u903b\u8f91\u63a8\u7406"] if zh else ["Basic high-school math", "Logical reasoning"]

        return {
            "domain": domain,
            "subject_family": family,
            "prerequisites": prereq,
            "assumptions": ["Deterministic scope fallback used."],
        }

    def _fallback_framework(self, normalized_topic: str, topic_type: str, language: str) -> Dict[str, Any]:
        zh = language == "zh-CN"
        if topic_type == "subject":
            if zh:
                return {
                    "style": "textbook",
                    "chapters": [
                        {"title": "\u57fa\u7840\u6982\u5ff5\u4e0e\u8bb0\u53f7", "sections": ["\u5b66\u79d1\u8303\u56f4", "\u6838\u5fc3\u672f\u8bed", "\u57fa\u672c\u5bf9\u8c61"]},
                        {"title": "\u57fa\u672c\u7406\u8bba\u4e0e\u7ed3\u6784", "sections": ["\u57fa\u672c\u6cd5\u5219", "\u5173\u952e\u547d\u9898", "\u7ed3\u6784\u6027\u7406\u89e3"]},
                        {"title": "\u6807\u51c6\u65b9\u6cd5\u4e0e\u89e3\u9898\u6d41\u7a0b", "sections": ["\u5e38\u7528\u65b9\u6cd5", "\u5178\u578b\u9898\u578b", "\u6b65\u9aa4\u5316\u6c42\u89e3"]},
                        {"title": "\u5e94\u7528\u573a\u666f\u4e0e\u7efc\u5408\u8bad\u7ec3", "sections": ["\u57fa\u7840\u5e94\u7528", "\u7efc\u5408\u6848\u4f8b", "\u8de8\u4e3b\u9898\u8fde\u63a5"]},
                        {"title": "\u8fdb\u9636\u4e13\u9898\u4e0e\u62d3\u5c55", "sections": ["\u9ad8\u9636\u4e3b\u9898", "\u7814\u7a76\u5bfc\u5411", "\u8fdb\u4e00\u6b65\u9605\u8bfb"]},
                    ],
                }
            return {
                "style": "textbook",
                "chapters": [
                    {"title": "Foundations and Notation", "sections": ["Scope of the subject", "Core terms", "Basic objects"]},
                    {"title": "Core Theory and Structure", "sections": ["Fundamental laws", "Key propositions", "Structural understanding"]},
                    {"title": "Standard Methods and Workflows", "sections": ["Canonical methods", "Typical problem types", "Step-by-step solving"]},
                    {"title": "Applications and Integrated Practice", "sections": ["Basic applications", "Integrated cases", "Cross-topic links"]},
                    {"title": "Advanced Topics and Extension", "sections": ["Advanced themes", "Research directions", "Further reading"]},
                ],
            }
        if zh:
            return {
                "style": "micro_curriculum",
                "modules": [
                    {"title": "\u6982\u5ff5\u5b9a\u4e49", "goal": f"\u51c6\u786e\u8bf4\u51fa {normalized_topic} \u7684\u5b9a\u4e49\u4e0e\u9002\u7528\u8fb9\u754c"},
                    {"title": "\u76f4\u89c9\u7406\u89e3", "goal": "\u5efa\u7acb\u5bf9\u6838\u5fc3\u601d\u60f3\u7684\u76f4\u89c9\u6a21\u578b"},
                    {"title": "\u524d\u7f6e\u77e5\u8bc6", "goal": "\u8865\u9f50\u7406\u89e3\u8be5\u77e5\u8bc6\u70b9\u9700\u8981\u7684\u57fa\u7840"},
                    {"title": "\u6838\u5fc3\u673a\u5236", "goal": "\u638c\u63e1\u63a8\u7406\u8fc7\u7a0b\u548c\u5173\u952e\u6b65\u9aa4"},
                    {"title": "\u4f8b\u9898\u6216\u5e94\u7528", "goal": "\u5728\u4ee3\u8868\u6027\u9898\u76ee/\u573a\u666f\u4e2d\u6b63\u786e\u4f7f\u7528"},
                    {"title": "\u5e38\u89c1\u9519\u8bef", "goal": "\u8bc6\u522b\u5e76\u907f\u514d\u9ad8\u9891\u8bef\u533a"},
                    {"title": "\u5ef6\u4f38\u4e3b\u9898", "goal": "\u5efa\u7acb\u4e0e\u76f8\u5173\u77e5\u8bc6\u7684\u8fc1\u79fb\u8fde\u63a5"},
                ],
            }
        return {
            "style": "micro_curriculum",
            "modules": [
                {"title": "Concept Definition", "goal": f"State the definition and boundary of {normalized_topic}"},
                {"title": "Intuitive Understanding", "goal": "Build a practical mental model of the idea"},
                {"title": "Prerequisite Knowledge", "goal": "Fill in minimum prerequisites before deep practice"},
                {"title": "Core Mechanism", "goal": "Master the key mechanism and reasoning steps"},
                {"title": "Examples or Applications", "goal": "Apply the concept on representative tasks"},
                {"title": "Common Mistakes", "goal": "Identify and avoid high-frequency errors"},
                {"title": "Extended Topics", "goal": "Connect this point to nearby advanced topics"},
            ],
        }

    @staticmethod
    def _extract_path_from_framework(framework: Dict[str, Any], topic_type: str) -> List[str]:
        if topic_type == "subject":
            chapters = framework.get("chapters", []) if isinstance(framework, dict) else []
            path = [str(c.get("title", "")).strip() for c in chapters if isinstance(c, dict) and str(c.get("title", "")).strip()]
            return path

        modules = framework.get("modules", []) if isinstance(framework, dict) else []
        path = [str(u.get("title", "")).strip() for u in modules if isinstance(u, dict) and str(u.get("title", "")).strip()]
        return path

    def normalize_topic_input(self, user_input: str, language: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_topic_intake_modules()
        result = self._topic_normalizer.run(user_input=user_input, language=language)  # type: ignore[attr-defined]
        return result

    def classify_topic_type(self, normalized_topic: str, user_input: str = "", language: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_topic_intake_modules()
        result = self._topic_classifier.run(  # type: ignore[attr-defined]
            normalized_topic=normalized_topic,
            user_input=user_input,
            language=language,
        )
        return result

    def infer_topic_scope(self, normalized_topic: str, topic_type: str, language: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_topic_intake_modules()
        result = self._scope_inference.run(  # type: ignore[attr-defined]
            normalized_topic=normalized_topic,
            topic_type=topic_type,
            language=language,
        )
        return result

    def build_learning_framework(
        self,
        normalized_topic: str,
        topic_type: str,
        scope_info: Dict[str, Any],
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_topic_intake_modules()
        result = self._framework_builder.run(  # type: ignore[attr-defined]
            normalized_topic=normalized_topic,
            topic_type=topic_type,
            scope_info=scope_info,
            language=language,
        )
        return result.get("framework", {})

    def _plan_learning_path_legacy(self, user_input: str) -> Dict[str, Any]:
        """Legacy deterministic workflow kept as a hard fallback."""
        lang = self._detect_input_language(user_input)

        try:
            normalized = self.normalize_topic_input(user_input=user_input, language=lang)
        except Exception as exc:
            logger.warning("normalize_topic_input failed: %s", exc)
            normalized = self._fallback_normalization(user_input=user_input, language=lang)

        normalized_topic = str(normalized.get("normalized_topic", user_input)).strip() or user_input
        lang = self._detect_input_language(normalized_topic, normalized.get("language", lang))

        try:
            classified = self.classify_topic_type(
                normalized_topic=normalized_topic,
                user_input=user_input,
                language=lang,
            )
        except Exception as exc:
            logger.warning("classify_topic_type failed: %s", exc)
            classified = self._fallback_classification(normalized_topic=normalized_topic, user_input=user_input, language=lang)

        topic_type = str(classified.get("topic_type", "knowledge_point")).strip().lower()
        if topic_type not in {"knowledge_point", "subject", "mixed", "invalid"}:
            topic_type = "knowledge_point"
        framework_topic_type = topic_type if topic_type in {"knowledge_point", "subject"} else "knowledge_point"

        try:
            scope = self.infer_topic_scope(
                normalized_topic=normalized_topic,
                topic_type=topic_type,
                language=lang,
            )
        except Exception as exc:
            logger.warning("infer_topic_scope failed: %s", exc)
            scope = self._fallback_scope(normalized_topic=normalized_topic, topic_type=topic_type, language=lang)

        try:
            framework = self.build_learning_framework(
                normalized_topic=normalized_topic,
                topic_type=framework_topic_type,
                scope_info=scope,
                language=lang,
            )
        except Exception as exc:
            logger.warning("build_learning_framework failed: %s", exc)
            framework = self._fallback_framework(normalized_topic=normalized_topic, topic_type=framework_topic_type, language=lang)

        path = self._extract_path_from_framework(
            framework=framework,
            topic_type=framework_topic_type,
        )
        if not path:
            path = [normalized_topic]

        assumptions: List[str] = []
        for src in [normalized, classified, scope]:
            vals = src.get("assumptions", []) if isinstance(src, dict) else []
            if isinstance(vals, list):
                assumptions.extend(str(v) for v in vals if str(v).strip())

        confidence = self._safe_confidence(min(
            self._safe_confidence(normalized.get("confidence", 0.6), 0.6),
            self._safe_confidence(classified.get("confidence", 0.6), 0.6),
        ))

        result: TopicAnalysisResult = {
            "normalized_topic": normalized_topic,
            "topic_type": topic_type,
            "domain": str(scope.get("domain", "General")),
            "subject_family": str(scope.get("subject_family", "General")),
            "aliases": normalized.get("aliases", []) if isinstance(normalized.get("aliases", []), list) else [],
            "confidence": confidence,
            "needs_clarification": bool(normalized.get("needs_clarification", False) or classified.get("needs_clarification", False)),
            "clarification_question": str(
                normalized.get("clarification_question")
                or classified.get("clarification_question")
                or ""
            ).strip(),
            "prerequisites": scope.get("prerequisites", []) if isinstance(scope.get("prerequisites", []), list) else [],
            "framework": framework,
            "path": path,
            "assumptions": assumptions or ["Deterministic fallback path extraction used."],
        }
        return result

    def plan_learning_path(self, user_input: str) -> Dict[str, Any]:
        """Plan a learning path via the staged orchestrator with a legacy fallback path."""
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

        try:
            self._ensure_learning_path_orchestrator()
            result = self._learning_path_orchestrator.plan_learning_path(user_input=user_input)  # type: ignore[attr-defined]
            if not isinstance(result, dict):
                raise TypeError("Learning path orchestrator returned a non-dict result.")

            missing = expected_keys.difference(result.keys())
            if missing:
                raise ValueError(f"Learning path orchestrator omitted keys: {sorted(missing)}")

            self._last_learning_path_trace = list(getattr(self._learning_path_orchestrator, "last_trace", []))  # type: ignore[attr-defined]
            self._last_learning_path_run_state = dict(getattr(self._learning_path_orchestrator, "last_run_state", {}))  # type: ignore[attr-defined]
            return {key: result[key] for key in expected_keys}
        except Exception as exc:
            logger.warning("Learning path orchestrator failed, falling back to legacy path: %s", exc)
            self._last_learning_path_trace = []
            self._last_learning_path_run_state = {}
            return self._plan_learning_path_legacy(user_input)

    def get_last_learning_path_trace(self) -> List[Dict[str, Any]]:
        return list(getattr(self, "_last_learning_path_trace", []))

    def get_last_learning_path_run_state(self) -> Dict[str, Any]:
        return dict(getattr(self, "_last_learning_path_run_state", {}))

    def get_topic_content(self, sub_topic: str) -> Dict[str, Any]:
        """Generate concise technical notes with LaTeX."""
        system_prompt = """You are a technical tutor writing concise, high-signal study notes.

Use an R1-style workflow internally, but do not expose reasoning.
Return only final content.

Requirements:
- English only.
- Markdown output.
- Keep it concise (120-220 words).
- Include at least one LaTeX expression when relevant.
- Structure: definition, key idea, one practical example.
"""
        user_prompt = f"Sub-topic: {sub_topic}"

        content = self._chat(
            model=self.model_chat,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=1000,
        )

        return {
            "sub_topic": sub_topic,
            "content_markdown": content.strip(),
        }

    def generate_exam(
        self,
        sub_topic: str,
        difficulty: str = "standard",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate 5 exam questions and persist them to cache."""
        level = difficulty.strip().lower() if difficulty else "standard"
        if level not in {"easy", "standard", "hard"}:
            level = "standard"
        output_language = self._resolve_output_language(language)

        system_prompt = f"""You are a NotebookLM-style assessment designer for technical learning.

Use an R1-style workflow:
1) Internally reason over concept coverage, difficulty, and common misconceptions.
2) Do not reveal your reasoning.
3) Output only final JSON.

Design exactly 5 questions for one sub-topic.
Mix question types when possible.

Output JSON schema:
[
  {{
    "question": "specific and technical question",
    "type": "choice or open",
    "options": ["A", "B", "C", "D"] or [],
    "hint": "short solving hint"
  }}
]

Rules:
- Keep all question text, options, and hints in {output_language}.
- Questions must be concrete, not generic.
- For choice questions, options must be plausible and mutually exclusive.
- No prose outside JSON.
"""

        user_prompt = (
            f"Sub-topic: {sub_topic}\n"
            f"Difficulty: {level}\n"
            f"Output language: {output_language}\n"
            "Generate exactly 5 questions."
        )

        raw = self._chat(
            model=self.model_reasoner,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=2200,
        )
        parsed = parse_llm_json(raw)

        questions: List[Dict[str, Any]] = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    normalized = self._normalize_question(item)
                    if normalized:
                        questions.append(normalized)

        questions = questions[:5]

        cache = self._read_cache()
        now = datetime.now(timezone.utc).isoformat()
        for q in questions:
            cache.append(
                {
                    "topic": sub_topic,
                    "difficulty": level,
                    "language": output_language,
                    "created_at": now,
                    "data": q,
                    "answered": False,
                    "result": None,
                    "user_answer": None,
                }
            )
        self._write_cache(cache)

        return {
            "sub_topic": sub_topic,
            "difficulty": level,
            "language": output_language,
            "questions": questions,
            "saved_to_cache": len(questions),
            "cache_file": str(CACHE_FILE),
        }

    def evaluate_and_update(self, user_answer: str, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate one answer and map score to Mastered/Reviewing/Failed."""
        question_text = str(question_data.get("question", "")).strip()
        sub_topic = str(question_data.get("sub_topic", question_data.get("topic", ""))).strip()
        reference_hint = str(question_data.get("hint", "")).strip()

        system_prompt = """You are a strict, fair technical grader.

Use an R1-style workflow internally.
Do not reveal your chain-of-thought.
Return only JSON.

Output JSON schema:
{
  "is_correct": true or false,
  "score": 0-100 integer,
  "feedback": "concise actionable feedback"
}

Scoring guide:
- 85-100: technically correct and complete
- 60-84: partially correct, notable gaps
- 0-59: incorrect or missing core understanding
"""
        user_prompt = (
            f"Sub-topic: {sub_topic}\n"
            f"Question: {question_text}\n"
            f"Reference hint: {reference_hint}\n"
            f"Learner answer: {user_answer}\n"
            "Evaluate now."
        )

        raw = self._chat(
            model=self.model_chat,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        parsed = parse_llm_json(raw)

        is_correct = False
        score = 0
        feedback = "Evaluation failed."

        if isinstance(parsed, dict):
            if isinstance(parsed.get("is_correct"), bool):
                is_correct = parsed["is_correct"]
            elif isinstance(parsed.get("is_correct"), str):
                is_correct = parsed["is_correct"].strip().lower() in {"true", "1", "yes"}

            try:
                score = int(parsed.get("score", 0))
            except Exception:
                score = 0
            score = max(0, min(100, score))

            feedback = str(parsed.get("feedback", "Evaluation complete.")).strip() or "Evaluation complete."

        if score >= 85:
            status = "Mastered"
        elif score >= 60:
            status = "Reviewing"
        else:
            status = "Failed"

        return {
            "status": status,
            "is_correct": is_correct,
            "score": score,
            "feedback": feedback,
        }


# ---------------------------------------------------------------------------
# Backward-compatible wrappers for existing API/UI calls
# ---------------------------------------------------------------------------

_ENGINE: Optional[LearningEngine] = None
_ENGINE_CONFIG_SIG: Optional[str] = None


def _build_engine_config_signature(engine_kwargs: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(engine_kwargs.get("base_url", "")),
            str(engine_kwargs.get("model_chat", "")),
            str(engine_kwargs.get("model_reasoner", "")),
            str(engine_kwargs.get("api_key", "")),
        ]
    )


def _engine_kwargs_from_user_context(user_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = user_context or {}
    provider = str(ctx.get("ai_provider", "deepseek")).strip().lower()
    api_key = str(ctx.get("ai_api_key", "")).strip()
    base_url = str(ctx.get("ai_base_url", "")).strip()
    model_chat = str(ctx.get("ai_model_chat", "")).strip()
    model_reasoner = str(ctx.get("ai_model_reasoner", "")).strip()

    if provider == "kimi":
        if not base_url:
            base_url = "https://api.moonshot.ai/v1"
        if not model_chat:
            model_chat = "kimi-k2-thinking-turbo"
        if not model_reasoner:
            model_reasoner = "kimi-k2-thinking"
    else:
        if not base_url:
            base_url = BASE_URL
        if not model_chat:
            model_chat = MODEL_CHAT
        if not model_reasoner:
            model_reasoner = MODEL_REASONER

    kwargs: Dict[str, Any] = {
        "base_url": base_url,
        "model_chat": model_chat,
        "model_reasoner": model_reasoner,
    }
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def _get_engine(**engine_kwargs: Any) -> LearningEngine:
    global _ENGINE
    global _ENGINE_CONFIG_SIG
    if not engine_kwargs:
        engine_kwargs = {
            "base_url": BASE_URL,
            "model_chat": MODEL_CHAT,
            "model_reasoner": MODEL_REASONER,
        }
    current_sig = _build_engine_config_signature(engine_kwargs)
    if _ENGINE is None or _ENGINE_CONFIG_SIG != current_sig:
        _ENGINE = LearningEngine(**engine_kwargs)
        _ENGINE_CONFIG_SIG = current_sig
    return _ENGINE


def _get_client() -> OpenAI:
    """Legacy helper kept for compatibility with existing scripts."""
    return _get_engine()._client


def _generate_questions_single_batch(
    topic: str,
    count: int,
    user_context: Optional[Dict[str, Any]] = None,
    mistake_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    engine = _get_engine(**_engine_kwargs_from_user_context(user_context))
    lang = (user_context or {}).get("language")
    result = engine.generate_exam(sub_topic=topic, difficulty="standard", language=lang)
    questions = result.get("questions", [])
    return questions[: max(1, min(count, len(questions)))]


def generate_questions_batch(
    topic: str,
    count: int = 15,
    user_context: Optional[Dict[str, Any]] = None,
    mistake_history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    engine = _get_engine(**_engine_kwargs_from_user_context(user_context))
    if count <= 0:
        return []
    lang = (user_context or {}).get("language")

    all_questions: List[Dict[str, Any]] = []
    while len(all_questions) < count:
        result = engine.generate_exam(sub_topic=topic, difficulty="standard", language=lang)
        batch = result.get("questions", [])
        if not isinstance(batch, list) or not batch:
            break
        all_questions.extend(batch)

    return all_questions[:count]


def evaluate_answer(
    topic: str,
    question: str,
    user_answer: str,
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    engine = _get_engine(**_engine_kwargs_from_user_context(user_context))
    result = engine.evaluate_and_update(
        user_answer=user_answer,
        question_data={"topic": topic, "question": question},
    )
    return {
        "is_correct": result.get("is_correct", False),
        "content": result.get("feedback", "Evaluation complete."),
        "status": result.get("status", "Failed"),
        "score": result.get("score", 0),
    }


def generate_explanation(topic: str, user_context: Optional[Dict[str, Any]] = None) -> str:
    engine = _get_engine(**_engine_kwargs_from_user_context(user_context))
    return engine.get_topic_content(topic).get("content_markdown", "")

