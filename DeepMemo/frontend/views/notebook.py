"""Notes and mistake notebook views."""

import time

import streamlit as st

from tools.utils import database


def render_logs() -> None:
    st.header("Study Notes")
    st.divider()

    with st.expander("New note", expanded=True):
        new_note = st.text_area("Content", height=100, placeholder="Record your learning notes...")
        if st.button("Save Note", use_container_width=True, type="primary"):
            if new_note.strip():
                database.add_note(new_note)
                st.success("Saved")
                time.sleep(0.5)
                st.rerun()

    st.divider()

    notes = database.get_all_notes()
    if not notes:
        st.info("No notes yet.")
        return

    for note_id, content, created_at in notes:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.caption(str(created_at))
            with col2:
                if st.button("Delete", key=f"del_note_{note_id}", use_container_width=True):
                    database.delete_note(note_id)
                    st.rerun()
            st.divider()
            st.markdown(content)


def render_mistakes() -> None:
    st.header("Mistake Review")
    st.divider()

    logs = database.get_mistake_details()
    if not logs:
        st.success("No mistakes yet. Keep going.")
        return

    st.info(f"{len(logs)} mistakes need review.")
    st.divider()

    for mistake_id, topic, question, user_answer, feedback, created_at in logs:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {topic}")
            with col2:
                st.caption(str(created_at)[:10])

            st.divider()
            st.markdown("**Question**")
            st.markdown(f"> {question}")
            st.markdown("**Your Answer**")
            st.markdown(f"> {user_answer}")
            st.markdown("**AI Feedback**")
            st.markdown(f"> {feedback}")
            st.divider()

            if st.button("Mark as Reviewed", key=f"rm_err_{mistake_id}", use_container_width=True):
                database.delete_mistake_log(mistake_id)
                st.rerun()
