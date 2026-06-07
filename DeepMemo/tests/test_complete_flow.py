from pathlib import Path

from tools.utils import config, database


def _reset_db() -> None:
    db_file = Path(config.DATABASE_FILE)
    if db_file.exists():
        db_file.unlink()


def test_database_learning_flow():
    _reset_db()
    database.create_tables()

    ok, _ = database.add_new_card("Test Topic", "For testing purposes")
    assert ok is True

    card_id = database.get_card_id_by_topic("Test Topic")
    assert card_id is not None

    before = database.get_today_review_count()
    database.record_study_log(card_id=card_id, result="correct")
    after = database.get_today_review_count()
    assert after == before + 1

    database.log_mistake(
        card_id=card_id,
        question="What is ML?",
        user_answer="Wrong answer",
        feedback="Machine Learning is a subset of AI",
    )
    queue = database.get_review_queue(limit=10)
    assert len(queue) >= 1

    database.delete_mistake_log(int(queue[0]["mistake_id"]))
    queue2 = database.get_review_queue(limit=10)
    assert len(queue2) <= len(queue)

