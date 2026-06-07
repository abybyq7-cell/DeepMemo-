"""Streamlit entrypoint for the DeepMemo learning app."""

from tools.utils import _encoding_fix  # noqa: F401

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import streamlit as st

from frontend.views import daily, library, notebook, settings
from tools.utils import database, session, styles
from tools.utils.config import ensure_data_dir
from tools.utils.i18n import t
from tools.utils.logging_config import setup_logging


setup_logging()
ensure_data_dir()

st.set_page_config(
    page_title="DeepMemo",
    layout="wide",
    page_icon="DM",
    initial_sidebar_state="expanded",
)

styles.inject_custom_css()
session.init()
st.session_state.today_count = database.get_today_review_count()

with st.sidebar:
    st.header("DeepMemo")
    st.divider()

    daily_limit = st.session_state.user_prefs.get("daily_limit", 5)
    today_count = st.session_state.today_count

    st.markdown(f"**{t('today_target')}**")
    st.progress(
        min(today_count / daily_limit, 1.0),
        text=f"{today_count}/{daily_limit} {t('questions_suffix')}",
    )

    st.divider()

    menu_items = [
        ("study", t("menu_study")),
        ("notes", t("menu_notes")),
        ("mistakes", t("menu_mistakes")),
        ("library", t("menu_library")),
        ("add", t("menu_add")),
        ("settings", t("menu_settings")),
    ]
    selected_label = st.radio(
        "Navigation",
        [label for _, label in menu_items],
        label_visibility="collapsed",
    )
    menu = next(key for key, label in menu_items if label == selected_label)

if menu == "study":
    daily.render()
elif menu == "notes":
    notebook.render_logs()
elif menu == "mistakes":
    notebook.render_mistakes()
elif menu == "library":
    library.render_list()
elif menu == "add":
    library.render_add()
elif menu == "settings":
    settings.render()
