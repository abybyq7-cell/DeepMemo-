from backend.scheduler_engine import schedule_next


def test_schedule_next_fallback_or_fsrs_shape():
    result = schedule_next(current_interval=2, is_correct=True, scheduler_state=None)
    assert isinstance(result.next_review_date, str)
    assert result.interval_days >= 1
    assert result.status in {"review", "learning"}


def test_schedule_next_incorrect_resets_learning():
    result = schedule_next(current_interval=10, is_correct=False, scheduler_state=None)
    assert result.status == "learning"
    assert result.interval_days >= 1


