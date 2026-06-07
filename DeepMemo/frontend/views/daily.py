"""Daily training view."""

import random
import streamlit as st

from tools.utils import api_client, database, question_cache
from tools.utils.config import MIN_CACHE_THRESHOLD, QUESTIONS_PER_BATCH
from tools.utils.i18n import t


def render():
    st.header(f"🧠 {t('daily_training')}")
    st.divider()

    review_queue = database.get_review_queue()
    if 'skip_review' not in st.session_state:
        st.session_state.skip_review = False

    if review_queue and not st.session_state.skip_review:
        _render_review_mode(review_queue)
    else:
        _render_study_mode()


def _render_review_mode(queue):
    mistake = queue[0]
    st.info(f"⚠️ 错题回顾 · 剩余 {len(queue)} 题")
    st.divider()

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**📌 {mistake['topic']}**")
        with col2:
            st.caption(f"📅 {mistake['create_time'][:10]}")

        st.markdown("**题目：**")
        st.markdown(f"> {mistake['question']}")
        st.markdown("**你之前的答案：**")
        st.markdown(f"> {mistake['user_answer']}")
        st.markdown("**反馈：**")
        st.markdown(f"> {mistake['feedback']}")

        user_answer = st.text_area(
            "重新作答",
            key=f"review_{mistake['mistake_id']}",
            height=100,
            label_visibility="collapsed",
            placeholder="输入你的答案...",
        )

        col_submit, col_skip = st.columns([1, 2])
        with col_submit:
            if st.button("提交答案", key=f"btn_submit_{mistake['mistake_id']}", use_container_width=True, type="primary"):
                if not user_answer.strip():
                    st.warning("请先输入答案")
                    return

                result = api_client.evaluate_answer(
                    mistake['topic'],
                    mistake['question'],
                    user_answer,
                    user_context=st.session_state.user_prefs,
                )
                if result and result.get('is_correct'):
                    st.success("回答正确")
                    st.markdown(result.get('content', ''))
                    card_id = database.get_card_id_by_topic(mistake['topic'])
                    database.record_study_log(card_id=card_id, result="correct_review")
                    database.delete_mistake_log(int(mistake["mistake_id"]))
                    st.rerun()
                else:
                    st.warning("答案仍不正确")
                    st.markdown(result.get('content', '') if result else "评判失败")

        with col_skip:
            if st.button("跳过错题，进入新题", use_container_width=True):
                st.session_state.skip_review = True
                st.rerun()


def _render_study_mode():
    if not st.session_state.daily_plan.get("is_initialized"):
        _initialize_study_plan()
        if st.session_state.daily_plan.get("is_initialized"):
            st.rerun()
        return

    plan = st.session_state.daily_plan
    topics = plan.get("topics", [])

    _prune_cache_for_selected_topics(topics)
    _ensure_cache_filled(plan)

    current_question = st.session_state.get("current_question")
    if not current_question:
        current_question = _pop_next_question_for_topics(topics)
        if not current_question:
            st.info("💡 AI 正在生成题目，请稍候...")
            return
        st.session_state.current_question = current_question
        st.session_state.question_result = None

    q_data = current_question.get("data", current_question)
    topic = current_question.get("topic") or q_data.get("topic") or "未分类"

    daily_limit = st.session_state.user_prefs.get('daily_limit', 5)
    progress = min(st.session_state.today_count / max(1, daily_limit), 1.0)
    cache_count = question_cache.get_cache_count()

    st.progress(progress)
    col_progress, col_cache = st.columns([2, 1])
    with col_progress:
        st.caption(f"今日进度：{st.session_state.today_count} / {daily_limit} 题")
    with col_cache:
        st.caption(f"缓存：{cache_count} 题")

    with st.container(border=True):
        st.markdown(f"### 📌 {topic}")
        st.markdown(q_data.get('question', '题目加载失败'))

        result = st.session_state.get("question_result")
        question_id = abs(hash(f"{topic}|{q_data.get('question', '')}"))

        if q_data.get('type') == 'choice':
            options = q_data.get('options', [])
            if not options:
                st.error("选择题缺少选项")
                return
            answer = st.radio(
                "请选择答案",
                options,
                key=f"q_choice_{question_id}",
                label_visibility="collapsed",
                disabled=bool(result),
            )
        else:
            answer = st.text_area(
                "请输入答案",
                key=f"q_text_{question_id}",
                label_visibility="collapsed",
                height=120,
                placeholder="输入你的答案...",
                disabled=bool(result),
            )

        submit_clicked = st.button(
            "提交答案",
            use_container_width=True,
            type="primary",
            key=f"btn_submit_{question_id}",
            disabled=bool(result),
        )

        if submit_clicked and not result:
            if not answer or not str(answer).strip():
                st.warning("请先输入/选择答案")
                return

            if q_data.get("answer"):
                evaluated = _evaluate_with_standard_answer(q_data, str(answer))
            else:
                with st.spinner("💡 AI 正在评判..."):
                    evaluated = api_client.evaluate_answer(
                        topic,
                        q_data.get('question', ''),
                        answer,
                        user_context=st.session_state.user_prefs,
                    )

            st.session_state.question_result = evaluated

            card_id = database.get_card_id_by_topic(topic)
            if evaluated and evaluated.get("is_correct"):
                database.record_study_log(card_id=card_id, result="correct")
            else:
                if card_id:
                    database.record_study_log(card_id=card_id, result="incorrect")
                    database.log_mistake(
                        card_id=card_id,
                        question=q_data.get("question", ""),
                        user_answer=str(answer),
                        feedback=evaluated.get("content", "评判失败") if evaluated else "评判失败",
                    )
            st.rerun()

        result = st.session_state.get("question_result")
        if result is not None:
            st.divider()
            if result.get("is_correct"):
                st.success("✅ 回答正确")
                st.markdown(f"**反馈：** {result.get('content', '做得很好')}" )
            else:
                st.warning("⚠️ 回答不正确")
                st.markdown(f"**反馈：** {result.get('content', '请再试一次')}" )

            col_retry, col_next = st.columns([1, 1])
            with col_retry:
                if st.button("🔁 再试一次", use_container_width=True, key=f"btn_retry_{question_id}"):
                    st.session_state.question_result = None
                    st.rerun()
            with col_next:
                if st.button("➡️ 下一题", use_container_width=True, key=f"btn_next_{question_id}"):
                    st.session_state.current_question = None
                    st.session_state.question_result = None
                    st.rerun()


def _initialize_study_plan():
    all_topics = database.get_all_topics()
    if not all_topics:
        st.warning(f"📚 {t('no_topics_in_library')}")
        return

    selected_topics = st.session_state.user_prefs.get("selected_topics", [])
    selected_topics = [topic for topic in selected_topics if topic in all_topics]
    if not selected_topics:
        st.warning(f"⚠️ {t('need_select_topics')}")
        return

    plan = st.session_state.daily_plan
    plan["topics"] = selected_topics
    plan["current_topic"] = selected_topics[0]
    plan["is_initialized"] = True

    st.session_state.current_question = None
    st.session_state.question_result = None
    st.info(f"✨ {t('plan_ready', count=len(selected_topics))}")


def _ensure_cache_filled(plan):
    cache_count = question_cache.get_cache_count()
    daily_limit = st.session_state.user_prefs.get('daily_limit', 5)
    needed_count = max(daily_limit + 5, QUESTIONS_PER_BATCH)

    if cache_count >= MIN_CACHE_THRESHOLD:
        return

    with st.spinner("💡 AI 正在生成题目..."):
        topics = plan.get("topics", [])
        for topic in topics:
            manual_questions = database.get_custom_questions_by_topic(topic, limit=20)
            if manual_questions:
                random.shuffle(manual_questions)
                wrapped_manual = [
                    {
                        "topic": topic,
                        "data": q,
                        "answered": False,
                        "result": None,
                        "user_answer": None,
                    }
                    for q in manual_questions
                ]
                question_cache.add_questions(wrapped_manual)

            mistake_history = database.get_topic_mistakes(topic) or []
            questions = api_client.generate_questions(
                topic=topic,
                count=needed_count,
                user_context=st.session_state.user_prefs,
                mistake_history=mistake_history,
            )

            if questions:
                wrapped = [
                    {
                        "topic": topic,
                        "data": q,
                        "answered": False,
                        "result": None,
                        "user_answer": None,
                    }
                    for q in questions
                ]
                question_cache.add_questions(wrapped)


def _prune_cache_for_selected_topics(selected_topics):
    allowed = {str(t).strip() for t in (selected_topics or []) if str(t).strip()}
    if not allowed:
        question_cache.clear_cache()
        return

    cache = question_cache.load_cache()
    if not cache:
        return

    filtered = []
    for item in cache:
        topic = ""
        if isinstance(item, dict):
            topic = str(item.get("topic", "")).strip()
            if not topic and isinstance(item.get("data"), dict):
                topic = str(item["data"].get("topic", "")).strip()
        if topic in allowed:
            filtered.append(item)

    if len(filtered) != len(cache):
        question_cache.save_cache(filtered)


def _pop_next_question_for_topics(selected_topics):
    allowed = {str(t).strip() for t in (selected_topics or []) if str(t).strip()}
    if not allowed:
        return None

    cache = question_cache.load_cache()
    if not cache:
        return None

    idx = None
    for i, item in enumerate(cache):
        topic = ""
        if isinstance(item, dict):
            topic = str(item.get("topic", "")).strip()
            if not topic and isinstance(item.get("data"), dict):
                topic = str(item["data"].get("topic", "")).strip()
        if topic in allowed:
            idx = i
            break

    if idx is None:
        return None

    question = cache.pop(idx)
    question_cache.save_cache(cache)
    return question


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _evaluate_with_standard_answer(q_data: dict, user_answer: str) -> dict:
    expected = _normalize_text(str(q_data.get("answer", "")))
    actual = _normalize_text(user_answer)

    if q_data.get("type") == "choice":
        is_correct = actual == expected
    else:
        keywords = [k.strip().lower() for k in expected.split("|") if k.strip()]
        if keywords:
            is_correct = any(k in actual for k in keywords)
        else:
            is_correct = actual == expected

    feedback = "回答正确" if is_correct else f"标准答案：{q_data.get('answer', '')}"
    return {"is_correct": is_correct, "content": feedback}

