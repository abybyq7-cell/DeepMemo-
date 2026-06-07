from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from tools.topic_intake import (
    FrameworkBuilderModule,
    ScopeInferenceModule,
    TopicClassifierModule,
    TopicNormalizerModule,
)
from tools.topic_intake.base import safe_confidence

from .base import build_result_path, detect_language, input_signature, topic_key_for
from .memory import LearningPathMemoryStore
from .state import LearningPathRunState


def _safe_float(value: object, default: float = 0.6) -> float:
    try:
        return float(value)
    except Exception:
        return default


class LearningPathOrchestrator:
    def __init__(
        self,
        chat_json: Callable[..., Optional[Any]],
        model_reasoner: str,
        memory_store: Optional[LearningPathMemoryStore] = None,
    ) -> None:
        self._chat_json = chat_json
        self._model_reasoner = model_reasoner
        self._normalizer = TopicNormalizerModule(chat_json, model_reasoner)
        self._classifier = TopicClassifierModule(chat_json, model_reasoner)
        self._scope_inference = ScopeInferenceModule(chat_json, model_reasoner)
        self._framework_builder = FrameworkBuilderModule(chat_json, model_reasoner)
        self._memory = memory_store or LearningPathMemoryStore()
        self.last_trace: list[dict[str, Any]] = []
        self.last_run_state: Dict[str, Any] = {}

    @classmethod
    def from_memory_file(
        cls,
        chat_json: Callable[..., Optional[Any]],
        model_reasoner: str,
        memory_file: Optional[Path] = None,
    ) -> "LearningPathOrchestrator":
        return cls(chat_json=chat_json, model_reasoner=model_reasoner, memory_store=LearningPathMemoryStore(memory_file))

    def _merge_assumptions(self, state: LearningPathRunState, *sources: Dict[str, Any]) -> None:
        for source in sources:
            if not isinstance(source, dict):
                continue
            assumptions = source.get("assumptions", [])
            if isinstance(assumptions, list):
                for item in assumptions:
                    state.add_assumption(str(item))

    def plan_learning_path(self, user_input: str, language: Optional[str] = None) -> Dict[str, Any]:
        lang = detect_language(user_input, language)
        state = LearningPathRunState(
            input_signature=input_signature(user_input),
            language=lang,
        )

        normalized = self._normalizer.run(user_input=user_input, language=lang)
        state.normalized_topic = str(normalized.get("normalized_topic", user_input)).strip() or user_input.strip()
        state.record_stage("normalize", "ok", normalized)

        normalized_language = str(normalized.get("language", lang) or lang)
        lang = detect_language(state.normalized_topic, normalized_language)
        state.language = lang
        state.topic_key = topic_key_for(state.normalized_topic, lang)
        classified = self._classifier.run(
            normalized_topic=state.normalized_topic,
            user_input=user_input,
            language=lang,
        )
        state.topic_type = str(classified.get("topic_type", "knowledge_point")).strip().lower() or "knowledge_point"
        if state.topic_type not in {"knowledge_point", "subject", "mixed", "invalid"}:
            state.topic_type = "knowledge_point"
        state.record_stage("classify", "ok", classified)
        framework_topic_type = state.topic_type if state.topic_type in {"subject", "knowledge_point"} else "knowledge_point"
        if framework_topic_type != state.topic_type:
            state.add_assumption("Framework generation downgraded to knowledge_point for compatibility.")

        memory_hit = False
        framework_result: Optional[Dict[str, Any]] = None
        memory_record = self._memory.get(state.normalized_topic, language=lang)
        compatible_memory = (
            isinstance(memory_record, dict)
            and memory_record.get("language") == lang
            and memory_record.get("topic_type") == state.topic_type
            and state.topic_type in {"subject", "knowledge_point"}
        )

        if compatible_memory:
            memory_hit = True
            scope = {
                "domain": memory_record.get("scope_info", {}).get("domain", ""),
                "subject_family": memory_record.get("scope_info", {}).get("subject_family", ""),
                "prerequisites": list(memory_record.get("prerequisites", [])),
                "assumptions": ["Reused scope memory."],
            }
            framework = memory_record.get("framework", {})
            if not isinstance(framework, dict):
                framework = {}
            state.memory_hit = True
            state.record_stage("memory", "hit", {"hit": True, "reused": True, "topic_key": state.topic_key, "scope_info": scope, "framework": framework}, memory_hit=True)
            self._memory.touch_reuse(state.normalized_topic, language=lang)
        else:
            scope = self._scope_inference.run(
                normalized_topic=state.normalized_topic,
                topic_type=state.topic_type,
                language=lang,
            )
            state.record_stage("scope", "ok", scope)
            framework_result = self._framework_builder.run(
                normalized_topic=state.normalized_topic,
                topic_type=framework_topic_type,
                scope_info=scope,
                language=lang,
            )
            state.record_stage("framework", "ok", framework_result)
            framework = framework_result.get("framework", {}) if isinstance(framework_result, dict) else {}

        if compatible_memory:
            state.record_stage("scope", "reused", scope, memory_hit=True)
            state.record_stage("framework", "reused", {"framework": framework, "assumptions": ["Reused framework memory."]}, memory_hit=True)

        if not isinstance(scope, dict):
            scope = {"domain": "General", "subject_family": "General", "prerequisites": [], "assumptions": []}
        if not isinstance(framework, dict):
            framework = {}

        path = build_result_path(framework, state.topic_type, state.normalized_topic)
        if not path:
            path = [state.normalized_topic] if state.normalized_topic else []

        self._merge_assumptions(state, normalized, classified, scope)
        if not compatible_memory and isinstance(framework_result, dict):
            self._merge_assumptions(state, framework_result)
        if compatible_memory:
            state.add_assumption("Topic memory reused for scope/framework.")
        else:
            state.add_assumption("Learning path generated via staged runtime.")

        result = {
            "normalized_topic": state.normalized_topic,
            "topic_type": state.topic_type,
            "domain": str(scope.get("domain", "General")),
            "subject_family": str(scope.get("subject_family", "General")),
            "aliases": normalized.get("aliases", []) if isinstance(normalized.get("aliases", []), list) else [],
            "confidence": safe_confidence(min(
                _safe_float(normalized.get("confidence", 0.6), 0.6),
                _safe_float(classified.get("confidence", 0.6), 0.6),
            )),
            "needs_clarification": bool(normalized.get("needs_clarification", False) or classified.get("needs_clarification", False)),
            "clarification_question": str(normalized.get("clarification_question") or classified.get("clarification_question") or "").strip(),
            "prerequisites": scope.get("prerequisites", []) if isinstance(scope.get("prerequisites", []), list) else [],
            "framework": framework if isinstance(framework, dict) else {},
            "path": path,
            "assumptions": [],
        }

        self._memory.upsert(
            normalized_topic=state.normalized_topic,
            language=lang,
            topic_type=state.topic_type,
            aliases=result["aliases"],
            confidence=float(result["confidence"]),
            scope_info=scope,
            framework=framework,
            prerequisites=result["prerequisites"],
            assumptions=state.assumptions,
            source="memory" if memory_hit else "model",
        )

        final_result = state.finalize_result(result)
        self.last_trace = state.trace_payload()
        self.last_run_state = state.run_state_payload()
        return final_result

    def run(self, user_input: str, language: Optional[str] = None) -> Dict[str, Any]:
        return self.plan_learning_path(user_input=user_input, language=language)

