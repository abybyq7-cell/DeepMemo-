"""Simple HTTP client to talk to the local FastAPI backend.

Provides fallback to local `ai_tutor` if the backend is unreachable.
"""
from typing import Any, Dict, List, Optional
import logging

import httpx
from tools.utils.config import API_BACKEND_URL

logger = logging.getLogger(__name__)
API_BASE = API_BACKEND_URL


def _post(path: str, json: Dict[str, Any], timeout: float = 10.0):
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=json)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.debug("POST %s failed: %s", url, e)
        return None


def _get(path: str, params: Dict[str, Any] = None, timeout: float = 10.0):
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.debug("GET %s failed: %s", url, e)
        return None


def generate_questions(topic: str, count: int = 15, user_context: Optional[Dict[str, Any]] = None, mistake_history: Optional[List[Any]] = None):
    payload = {"topic": topic, "count": count, "user_context": user_context or {}}
    resp = _post("/generate", payload)
    if resp and "questions" in resp:
        return resp["questions"]

    # Fallback to local ai_tutor if available
    try:
        import ai_tutor
        return ai_tutor.generate_questions_batch(topic, count, user_context, mistake_history)
    except Exception:
        return []


def evaluate_answer(topic: str, question: str, user_answer: str, user_context: Optional[Dict[str, Any]] = None):
    payload = {"topic": topic, "question": question, "user_answer": user_answer, "user_context": user_context or {}}
    resp = _post("/evaluate", payload)
    if resp:
        return resp

    try:
        import ai_tutor
        return ai_tutor.evaluate_answer(topic, question, user_answer, user_context=user_context)
    except Exception:
        return {"is_correct": False, "content": "Evaluation failed"}


def generate_explanation(topic: str, user_context: Optional[Dict[str, Any]] = None):
    payload = {"topic": topic, "user_context": user_context or {}}
    resp = _post("/explain", payload)
    if resp and "explanation" in resp:
        return resp["explanation"]

    try:
        import ai_tutor
        return ai_tutor.generate_explanation(topic, user_context=user_context)
    except Exception:
        return ""

