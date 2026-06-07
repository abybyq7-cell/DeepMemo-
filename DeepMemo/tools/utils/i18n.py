"""Minimal Streamlit i18n helper."""

import streamlit as st


TRANSLATIONS = {
    "zh": {
        "today_target": "今日目标完成度",
        "questions_suffix": "题",
        "menu_study": "刷题",
        "menu_notes": "笔记",
        "menu_mistakes": "错题",
        "menu_library": "知识库",
        "menu_add": "添加知识",
        "menu_settings": "设置",
        "daily_training": "今日特训",
        "need_select_topics": "请先在设置里手动选择学习主题，系统不会自动选题。",
        "no_topics_in_library": "请先在知识库中添加主题，再到设置中选择学习主题。",
        "plan_ready": "已加载 {count} 个手动选择的主题，开始学习吧。",
        "language": "语言",
        "language_zh": "中文",
        "language_en": "English",
        "selected_topics": "学习主题（手动选择）",
        "selected_topics_help": "只会从你手动勾选的主题出题，不会自动随机选择。",
    },
    "en": {
        "today_target": "Today's Progress",
        "questions_suffix": "questions",
        "menu_study": "Practice",
        "menu_notes": "Notes",
        "menu_mistakes": "Mistakes",
        "menu_library": "Library",
        "menu_add": "Add Knowledge",
        "menu_settings": "Settings",
        "daily_training": "Daily Training",
        "need_select_topics": "Please select study topics manually in Settings. The app will not auto-pick topics.",
        "no_topics_in_library": "Please add topics in Library first, then select topics in Settings.",
        "plan_ready": "{count} manually selected topics loaded. Ready to study.",
        "language": "Language",
        "language_zh": "Chinese",
        "language_en": "English",
        "selected_topics": "Study Topics (Manual)",
        "selected_topics_help": "Questions will be generated only from manually selected topics.",
    },
}


def get_language() -> str:
    prefs = st.session_state.get("user_prefs", {})
    return prefs.get("language", "zh")


def t(key: str, **kwargs) -> str:
    lang = get_language()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["zh"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
