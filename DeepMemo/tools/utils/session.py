"""Streamlit session-state helpers."""

import streamlit as st

from tools.utils import database
from tools.utils.config import DEFAULT_USER_PREFS
from tools.utils.user_prefs_store import load_user_prefs


def init() -> None:
    """Initialize database tables and default Streamlit state."""
    database.create_table()

    if "user_prefs" not in st.session_state:
        st.session_state.user_prefs = load_user_prefs()
    else:
        for key, value in DEFAULT_USER_PREFS.items():
            st.session_state.user_prefs.setdefault(key, value)

    defaults = {
        "today_count": database.get_today_review_count(),
        "review_stage": "question",
        "current_task": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    st.session_state.setdefault(
        "daily_plan",
        {
            "topics": [],
            "current_topic_idx": 0,
            "current_q_idx": 0,
            "questions_by_topic": {},
            "is_initialized": False,
            "questions_per_topic": 3,
            "generation_status": {"started": False, "done": False, "error": None},
        },
    )


def get_context() -> dict:
    prefs = st.session_state.get("user_prefs", {})
    return {
        "role": prefs.get("user_role", "student"),
        "field": prefs.get("user_field", "general knowledge"),
        "style": prefs.get("learning_style", "Socratic"),
    }
