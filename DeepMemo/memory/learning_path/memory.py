from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .base import build_result_path, summarize_framework, summarize_scope, topic_key_for, utc_now_iso


class LearningPathMemoryStore:
    VERSION = 1

    def __init__(self, memory_file: Optional[Path] = None) -> None:
        if memory_file is None:
            memory_file = Path(__file__).resolve().parents[2] / "data" / "learning_path_memory.json"
        self.memory_file = memory_file

    def _empty_payload(self) -> Dict[str, Any]:
        return {"version": self.VERSION, "topics": {}}

    def load(self) -> Dict[str, Any]:
        try:
            if not self.memory_file.exists():
                return self._empty_payload()
            with self.memory_file.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict) and isinstance(data.get("topics"), dict):
                data.setdefault("version", self.VERSION)
                return data
        except Exception:
            pass
        return self._empty_payload()

    def save(self, payload: Dict[str, Any]) -> None:
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.memory_file.with_suffix(self.memory_file.suffix + ".tmp")
        with tmp_file.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
        tmp_file.replace(self.memory_file)

    def get(self, topic: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        key = topic_key_for(topic, language)
        if not key:
            return None
        payload = self.load()
        topics = payload.get("topics", {})
        if not isinstance(topics, dict):
            return None
        item = topics.get(key)
        if isinstance(item, dict):
            return item
        return None

    def upsert(
        self,
        *,
        normalized_topic: str,
        language: str,
        topic_type: str,
        aliases: Optional[list[str]] = None,
        confidence: float = 0.0,
        scope_info: Optional[Dict[str, Any]] = None,
        framework: Optional[Dict[str, Any]] = None,
        prerequisites: Optional[list[str]] = None,
        assumptions: Optional[list[str]] = None,
        source: str = "model",
    ) -> Dict[str, Any]:
        topic_key = topic_key_for(normalized_topic, language)
        payload = self.load()
        topics = payload.setdefault("topics", {})
        if not isinstance(topics, dict):
            topics = {}
            payload["topics"] = topics

        existing = topics.get(topic_key, {}) if topic_key else {}
        reused_count = int(existing.get("reused_count", 0)) if isinstance(existing, dict) else 0

        scope_block = summarize_scope(scope_info or {})
        framework_block = summarize_framework(framework or {})
        path = build_result_path(framework or {}, topic_type, normalized_topic)

        record = {
            "topic_key": topic_key,
            "normalized_topic": normalized_topic,
            "language": language,
            "topic_type": topic_type,
            "aliases": aliases or [],
            "confidence": confidence,
            "scope_info": scope_info or {},
            "scope_summary": scope_block,
            "framework": framework or {},
            "framework_summary": framework_block,
            "path": path,
            "prerequisites": prerequisites or [],
            "assumptions": assumptions or [],
            "source": source,
            "reused_count": reused_count,
            "updated_at": utc_now_iso(),
        }
        topics[topic_key] = record
        self.save(payload)
        return record

    def touch_reuse(self, topic: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        key = topic_key_for(topic, language)
        if not key:
            return None
        payload = self.load()
        topics = payload.get("topics", {})
        if not isinstance(topics, dict):
            return None
        record = topics.get(key)
        if not isinstance(record, dict):
            return None
        record["reused_count"] = int(record.get("reused_count", 0)) + 1
        record["last_used_at"] = utc_now_iso()
        topics[key] = record
        self.save(payload)
        return record

    def describe(self, topic: str, language: Optional[str] = None) -> Dict[str, Any]:
        record = self.get(topic, language)
        if not isinstance(record, dict):
            return {"hit": False, "topic_key": topic_key_for(topic, language)}
        return {
            "hit": True,
            "topic_key": record.get("topic_key", ""),
            "topic_type": record.get("topic_type", ""),
            "reused_count": record.get("reused_count", 0),
            "scope_summary": record.get("scope_summary", {}),
            "framework_summary": record.get("framework_summary", {}),
        }
