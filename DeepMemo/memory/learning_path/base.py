from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from tools.topic_intake.base import canonicalize_topic_text, detect_language


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def topic_key_for(topic: str, language: Optional[str] = None) -> str:
    canonical = canonicalize_topic_text(topic)
    lang = detect_language(canonical or topic, language)
    normalized = " ".join((canonical or "").strip().lower().split())
    if not normalized:
        return ""
    return f"{lang}::{normalized}"


def input_signature(text: str) -> str:
    normalized = " ".join((text or "").strip().split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def short_text(value: object, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def compact_list(values: object, limit: int = 4) -> List[str]:
    if not isinstance(values, list):
        return []
    items = [short_text(item, 40) for item in values if short_text(item, 40)]
    return items[:limit]


def compact_mapping(payload: object, keys: Iterable[str], limit: int = 120) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, list):
            out[key] = compact_list(value)
        elif isinstance(value, dict):
            out[key] = {
                sub_key: short_text(sub_value, limit)
                for sub_key, sub_value in list(value.items())[:4]
            }
        else:
            out[key] = short_text(value, limit)
    return out


def summarize_scope(scope_info: object) -> Dict[str, Any]:
    if not isinstance(scope_info, dict):
        return {}
    return {
        "domain": short_text(scope_info.get("domain", "")),
        "subject_family": short_text(scope_info.get("subject_family", "")),
        "prerequisites": compact_list(scope_info.get("prerequisites", []), limit=4),
    }


def summarize_framework(framework: object) -> Dict[str, Any]:
    if not isinstance(framework, dict):
        return {}
    style = short_text(framework.get("style", ""))
    if style == "textbook":
        chapters = framework.get("chapters", [])
        return {
            "style": style,
            "chapter_count": len(chapters) if isinstance(chapters, list) else 0,
            "chapters": [
                {
                    "title": short_text(item.get("title", ""), 60),
                    "sections": compact_list(item.get("sections", []), limit=3),
                }
                for item in chapters[:4]
                if isinstance(item, dict) and short_text(item.get("title", ""), 60)
            ],
        }

    modules = framework.get("modules", [])
    return {
        "style": style,
        "module_count": len(modules) if isinstance(modules, list) else 0,
        "modules": [
            {
                "title": short_text(item.get("title", ""), 60),
                "goal": short_text(item.get("goal", ""), 90),
            }
            for item in modules[:5]
            if isinstance(item, dict) and short_text(item.get("title", ""), 60)
        ],
    }


def summarize_module_output(stage: str, output: object) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return {"stage": stage, "summary": short_text(output, 160)}

    summary: Dict[str, Any] = {"stage": stage}
    if stage == "normalize":
        summary.update(
            compact_mapping(
                output,
                ["normalized_topic", "language", "confidence", "needs_clarification", "clarification_question"],
            )
        )
        summary["aliases"] = compact_list(output.get("aliases", []), limit=4)
        summary["assumptions"] = compact_list(output.get("assumptions", []), limit=3)
    elif stage == "classify":
        summary.update(
            compact_mapping(
                output,
                ["topic_type", "confidence", "needs_clarification", "clarification_question"],
            )
        )
        summary["assumptions"] = compact_list(output.get("assumptions", []), limit=3)
    elif stage == "scope":
        summary.update(summarize_scope(output))
        summary["assumptions"] = compact_list(output.get("assumptions", []), limit=3)
    elif stage == "framework":
        summary.update(summarize_framework(output.get("framework", output)))
        summary["assumptions"] = compact_list(output.get("assumptions", []), limit=3)
    elif stage == "memory":
        summary.update(
            {
                "topic_key": short_text(output.get("topic_key", "")),
                "reuse": bool(output.get("reused", False)),
                "hit": bool(output.get("hit", False)),
            }
        )
        if output.get("scope_info"):
            summary["scope"] = summarize_scope(output.get("scope_info"))
        if output.get("framework"):
            summary["framework"] = summarize_framework(output.get("framework"))
    else:
        summary["summary"] = short_text(output, 160)

    return summary


def build_result_path(framework: object, topic_type: str, normalized_topic: str) -> List[str]:
    if not isinstance(framework, dict):
        return [normalized_topic] if normalized_topic else []

    if topic_type == "subject":
        chapters = framework.get("chapters", [])
        if isinstance(chapters, list):
            titles = [
                short_text(item.get("title", ""), 80)
                for item in chapters
                if isinstance(item, dict) and short_text(item.get("title", ""), 80)
            ]
            if titles:
                return titles
    modules = framework.get("modules", [])
    if isinstance(modules, list):
        titles = [
            short_text(item.get("title", ""), 80)
            for item in modules
            if isinstance(item, dict) and short_text(item.get("title", ""), 80)
        ]
        if titles:
            return titles
    return [normalized_topic] if normalized_topic else []

