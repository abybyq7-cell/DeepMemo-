from tools.utils import question_cache


def test_cache_add_and_pop():
    question_cache.clear_cache()
    question_cache.add_questions([{"id": 1}, {"id": 2}])

    assert question_cache.get_cache_count() == 2
    popped = question_cache.pop_question()
    assert popped == {"id": 1}
    assert question_cache.get_cache_count() == 1


