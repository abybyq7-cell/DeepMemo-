"""Spaced repetition scheduling engine.

Primary strategy: FSRS (if installed).
Fallback strategy: simple interval doubling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduleResult:
    next_review_date: str
    interval_days: int
    status: str
    scheduler_state: Optional[str]


def _fallback_schedule(current_interval: int, is_correct: bool) -> ScheduleResult:
    today = date.today()
    if is_correct:
        interval_days = max(1, min(current_interval * 2, 365))
        status = "review"
    else:
        interval_days = 1
        status = "learning"
    due = today + timedelta(days=interval_days)
    return ScheduleResult(
        next_review_date=due.isoformat(),
        interval_days=interval_days,
        status=status,
        scheduler_state=None,
    )


def schedule_next(
    current_interval: int,
    is_correct: bool,
    scheduler_state: Optional[str] = None,
) -> ScheduleResult:
    """Compute next schedule based on answer correctness."""
    try:
        from fsrs import Card, Rating, Scheduler  # type: ignore
    except Exception:
        logger.debug("fsrs not available; using fallback scheduler")
        return _fallback_schedule(current_interval, is_correct)

    try:
        scheduler = Scheduler()
        if scheduler_state:
            card = Card.from_json(json.loads(scheduler_state))
        else:
            card = Card()
        rating = Rating.Good if is_correct else Rating.Again
        card, _ = scheduler.review_card(card, rating)
        due_dt = card.due
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        interval_days = max(1, (due_dt.date() - datetime.now(timezone.utc).date()).days)
        return ScheduleResult(
            next_review_date=due_dt.date().isoformat(),
            interval_days=interval_days,
            status="review" if is_correct else "learning",
            scheduler_state=json.dumps(card.to_json(), ensure_ascii=False),
        )
    except Exception as e:
        logger.exception("fsrs scheduling failed, fallback to default: %s", e)
        return _fallback_schedule(current_interval, is_correct)

