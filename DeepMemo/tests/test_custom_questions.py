from tools.utils import database


def test_add_and_get_custom_question():
    database.create_tables()
    ok, _ = database.add_custom_question(
        topic="Test Topic",
        question="2+2=?",
        question_type="choice",
        options=["3", "4", "5"],
        standard_answer="4",
    )
    assert ok is True
    rows = database.get_custom_questions_by_topic("Test Topic", limit=20)
    assert rows
    assert rows[0]["question"]
    assert "answer" in rows[0]


