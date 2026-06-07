from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import summarize_module_output, utc_now_iso


@dataclass
class StageTraceEntry:
    stage: str
    status: str
    summary: Dict[str, Any]
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class LearningPathRunState:
    input_signature: str
    language: str
    normalized_topic: str = ""
    topic_type: str = ""
    topic_key: str = ""
    trace: List[StageTraceEntry] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    memory_hit: bool = False

    def add_assumption(self, text: str) -> None:
        value = str(text or "").strip()
        if value and value not in self.assumptions:
            self.assumptions.append(value)

    def record_stage(self, stage: str, status: str, output: object, *, memory_hit: bool = False) -> None:
        summary = summarize_module_output(stage, output)
        if memory_hit:
            summary["memory_hit"] = True
        self.trace.append(
            StageTraceEntry(
                stage=stage,
                status=status,
                summary=summary,
            )
        )

    def trace_payload(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage": item.stage,
                "status": item.status,
                "summary": item.summary,
                "timestamp": item.timestamp,
            }
            for item in self.trace
        ]

    def run_state_payload(self) -> Dict[str, Any]:
        return {
            "input_signature": self.input_signature,
            "language": self.language,
            "normalized_topic": self.normalized_topic,
            "topic_type": self.topic_type,
            "topic_key": self.topic_key,
            "memory_hit": self.memory_hit,
        }

    def finalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(result)
        if self.assumptions:
            existing = out.get("assumptions", [])
            if isinstance(existing, list):
                merged = list(existing)
            else:
                merged = []
            for item in self.assumptions:
                if item not in merged:
                    merged.append(item)
            out["assumptions"] = merged
        return out
