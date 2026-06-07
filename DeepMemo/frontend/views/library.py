"""Knowledge library views."""

import time

import streamlit as st

from tools.utils import api_client, database
from tools.utils.user_prefs_store import save_user_prefs


def render_list() -> None:
    st.header("Knowledge Library")
    st.divider()

    search = st.text_input("Search knowledge points", placeholder="Type a keyword...")
    cards = database.get_cards_by_type("all")
    filtered = [
        card
        for card in cards
        if not search or search.lower() in str(card[1]).lower() or search.lower() in str(card[2]).lower()
    ]

    if not filtered:
        st.info("No knowledge cards yet. Add one first.")
        return

    st.caption(f"{len(filtered)} knowledge points")
    st.divider()

    for card_id, topic, explanation, *_ in filtered:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {topic}")
            with col2:
                if st.button("Delete", key=f"del_card_{card_id}", use_container_width=True):
                    database.delete_card(card_id)
                    prefs = st.session_state.get("user_prefs", {})
                    selected_topics = prefs.get("selected_topics", [])
                    if isinstance(selected_topics, list) and topic in selected_topics:
                        prefs["selected_topics"] = [item for item in selected_topics if item != topic]
                        st.session_state.user_prefs = prefs
                        save_user_prefs(prefs)
                        if "daily_plan" in st.session_state:
                            st.session_state.daily_plan["is_initialized"] = False
                    st.rerun()
            st.divider()
            st.markdown(explanation or "")


def render_add() -> None:
    st.header("Add Knowledge")
    st.divider()

    with st.container(border=True):
        topic = st.text_input("Topic", placeholder="e.g. Linear Algebra")
        col_generate, col_manual = st.columns([1, 1])

        with col_generate:
            if st.button("Generate Note with AI", use_container_width=True, type="primary"):
                if not topic.strip():
                    st.warning("Please enter a topic first.")
                else:
                    with st.spinner("Generating note..."):
                        note = api_client.generate_explanation(
                            topic,
                            user_context=st.session_state.user_prefs,
                        )
                        st.session_state.new_note_cache = {"t": topic, "c": note}

        with col_manual:
            if st.button("Write Manually", use_container_width=True):
                st.session_state.new_note_cache = {"t": topic, "c": ""}

    st.divider()

    if "new_note_cache" in st.session_state:
        data = st.session_state.new_note_cache
        with st.container(border=True):
            content = st.text_area(
                "Note content",
                value=data["c"],
                height=280,
                placeholder="Write or edit the generated note...",
            )
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                if st.button("Save Knowledge", use_container_width=True, type="primary"):
                    if not content.strip():
                        st.warning("Content cannot be empty.")
                    else:
                        database.add_new_card(data["t"], content)
                        del st.session_state.new_note_cache
                        st.success("Saved")
                        time.sleep(0.5)
                        st.rerun()
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    del st.session_state.new_note_cache
                    st.rerun()

    st.divider()
    _render_custom_question_editor()


def _render_custom_question_editor() -> None:
    st.subheader("Add Custom Questions")
    topics = database.get_all_topics()
    if not topics:
        st.info("Add at least one knowledge topic before creating questions.")
        return

    with st.container(border=True):
        topic = st.selectbox("Topic", options=topics, key="custom_q_topic")
        q_type = st.selectbox(
            "Question type",
            options=["choice", "open"],
            format_func=lambda value: "Choice" if value == "choice" else "Open",
        )
        question = st.text_area("Question", placeholder="Type the question...", height=100, key="custom_q_question")

        options = []
        if q_type == "choice":
            st.caption("Choice options. At least two are required.")
            options = [
                st.text_input("Option A", key="custom_opt_a"),
                st.text_input("Option B", key="custom_opt_b"),
                st.text_input("Option C (optional)", key="custom_opt_c"),
                st.text_input("Option D (optional)", key="custom_opt_d"),
            ]

        standard_answer = st.text_input(
            "Standard answer",
            placeholder="For choice questions, enter the full correct option text.",
            key="custom_standard_answer",
        )

        if st.button("Save Question", type="primary", use_container_width=True, key="save_custom_q"):
            if not question.strip() or not standard_answer.strip():
                st.warning("Question and standard answer cannot be empty.")
            else:
                ok, msg = database.add_custom_question(
                    topic=topic,
                    question=question,
                    question_type=q_type,
                    options=options,
                    standard_answer=standard_answer,
                )
                st.success(msg) if ok else st.error(msg)

    saved = database.get_custom_questions_by_topic(topic, limit=10)
    if saved:
        st.caption(f"Recent questions for {topic}")
        for item in saved:
            with st.container(border=True):
                st.markdown(f"**Question:** {item['question']}")
                if item["type"] == "choice" and item["options"]:
                    st.markdown(" / ".join(item["options"]))
                st.markdown(f"**Answer:** {item['answer']}")
