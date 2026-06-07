"""Local JSON cache for generated questions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tools.utils.config import CACHE_FILE, ensure_cache_dir


logger = logging.getLogger(__name__)


def load_cache() -> List[Dict[str, Any]]:
    try:
        ensure_cache_dir()
        if not CACHE_FILE.exists():
            return []
        with CACHE_FILE.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.exception("Failed to load question cache: %s", exc)
        return []


def save_cache(questions: list) -> bool:
    try:
        ensure_cache_dir()
        with CACHE_FILE.open("w", encoding="utf-8") as fp:
            json.dump(questions, fp, ensure_ascii=False, indent=2)
        logger.info("Saved %s questions to cache", len(questions))
        return True
    except Exception as exc:
        logger.exception("Failed to save question cache: %s", exc)
        return False


def add_questions(new_questions: list) -> None:
    if not new_questions:
        return
    cache = load_cache()
    cache.extend(new_questions)
    save_cache(cache)
    logger.info("Added %s questions to cache; total=%s", len(new_questions), len(cache))


def pop_question() -> Optional[Dict[str, Any]]:
    cache = load_cache()
    if not cache:
        logger.warning("Question cache is empty")
        return None
    question = cache.pop(0)
    save_cache(cache)
    logger.info("Popped one question; remaining=%s", len(cache))
    return question if isinstance(question, dict) else {"value": question}


def get_cache_count() -> int:
    return len(load_cache())


def clear_cache() -> None:
    save_cache([])
    logger.info("Question cache cleared")


def cache_status() -> dict:
    return {
        "count": get_cache_count(),
        "file_path": str(CACHE_FILE),
        "exists": CACHE_FILE.exists(),
    }


def remove_questions_by_topic(topic: str) -> int:
    target = (topic or "").strip().lower()
    if not target:
        return 0

    cache = load_cache()
    kept = []
    removed = 0
    for item in cache:
        entry_topic = ""
        if isinstance(item, dict):
            top_topic = item.get("topic")
            data = item.get("data")
            data_topic = data.get("topic") if isinstance(data, dict) else None
            if isinstance(top_topic, str):
                entry_topic = top_topic
            elif isinstance(data_topic, str):
                entry_topic = data_topic

        if entry_topic.strip().lower() == target:
            removed += 1
        else:
            kept.append(item)

    if removed:
        save_cache(kept)
        logger.info("Removed %s cached questions for topic=%s", removed, topic)
    return removed
