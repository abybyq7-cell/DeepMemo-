import streamlit as st
from tools.utils import database, question_cache
from tools.utils.i18n import t
from tools.utils.user_prefs_store import save_user_prefs


def _persist_user_prefs() -> None:
    save_user_prefs(st.session_state.user_prefs)


def render() -> None:
    st.header("⚙️ 偏好设置")
    st.divider()

    # 语言设置
    with st.container(border=True):
        st.markdown(f"### 🌐 {t('language')}")
        current_lang = st.session_state.user_prefs.get("language", "zh")
        lang_options = {"zh": t("language_zh"), "en": t("language_en")}
        selected_label = st.selectbox(
            t("language"),
            options=[lang_options["zh"], lang_options["en"]],
            index=0 if current_lang == "zh" else 1,
        )
        selected_lang = "zh" if selected_label == lang_options["zh"] else "en"
        if selected_lang != current_lang:
            st.session_state.user_prefs["language"] = selected_lang
            _persist_user_prefs()
            st.rerun()

    st.divider()

    # 用户身份和领域设置
    with st.container(border=True):
        st.markdown("### 👤 个人信息")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            role = st.text_input(
                "身份/职位",
                value=st.session_state.user_prefs.get("user_role", "大学生"),
                placeholder="例如：大学生、工程师...",
            )
        with col2:
            field = st.text_input(
                "学习领域",
                value=st.session_state.user_prefs.get("user_field", "通识教育"),
                placeholder="例如：计算机、医学...",
            )

        if role != st.session_state.user_prefs.get("user_role", "大学生") or field != st.session_state.user_prefs.get("user_field", "通识教育"):
            st.session_state.user_prefs.update({"user_role": role, "user_field": field})
            _persist_user_prefs()
            st.success("✅ 个人信息已保存")

    st.divider()

    # 学习目标设置
    with st.container(border=True):
        st.markdown("### 🎯 学习目标")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            daily_limit = st.number_input(
                "每日学习上限 (题)",
                min_value=5,
                max_value=200,
                value=st.session_state.user_prefs.get("daily_limit", 15),
                step=5,
                help="每天需要完成的题目数量",
            )
        with col2:
            questions_per_topic = st.number_input(
                "每个主题的题量",
                min_value=1,
                max_value=10,
                value=st.session_state.user_prefs.get("daily_questions_per_topic", 3),
                help="从每个主题中生成多少题",
            )

        if (
            daily_limit != st.session_state.user_prefs.get("daily_limit", 15)
            or questions_per_topic != st.session_state.user_prefs.get("daily_questions_per_topic", 3)
        ):
            st.session_state.user_prefs.update(
                {
                    "daily_limit": daily_limit,
                    "daily_questions_per_topic": questions_per_topic,
                }
            )
            _persist_user_prefs()
            st.success("✅ 学习目标已保存")

    st.divider()

    # 主题手动选择
    with st.container(border=True):
        st.markdown(f"### 📚 {t('selected_topics')}")
        all_topics = database.get_all_topics()
        selected_topics = st.multiselect(
            t("selected_topics"),
            options=all_topics,
            default=[
                topic
                for topic in st.session_state.user_prefs.get("selected_topics", [])
                if topic in all_topics
            ],
            help=t("selected_topics_help"),
            label_visibility="collapsed",
        )
        if selected_topics != st.session_state.user_prefs.get("selected_topics", []):
            st.session_state.user_prefs["selected_topics"] = selected_topics
            _persist_user_prefs()
            st.session_state.daily_plan["is_initialized"] = False
            st.success("✅ 主题选择已保存")

    st.divider()

    # AI 模型设置
    with st.container(border=True):
        st.markdown("### 🤖 AI 模型")

        provider_options = {
            "deepseek": "DeepSeek",
            "kimi": "Kimi (Moonshot)",
        }
        current_provider = str(st.session_state.user_prefs.get("ai_provider", "deepseek")).strip().lower()
        if current_provider not in provider_options:
            current_provider = "deepseek"

        selected_provider = st.selectbox(
            "模型提供方",
            options=list(provider_options.keys()),
            index=0 if current_provider == "deepseek" else 1,
            format_func=lambda x: provider_options.get(x, x),
        )

        default_base_url = "https://api.deepseek.com" if selected_provider == "deepseek" else "https://api.moonshot.ai/v1"
        default_chat_model = "deepseek-chat" if selected_provider == "deepseek" else "kimi-k2-thinking-turbo"
        default_reasoner_model = "deepseek-reasoner" if selected_provider == "deepseek" else "kimi-k2-thinking"
        provider_switched = selected_provider != current_provider
        if provider_switched:
            st.session_state.user_prefs.update(
                {
                    "ai_provider": selected_provider,
                    "ai_base_url": default_base_url,
                    "ai_model_chat": default_chat_model,
                    "ai_model_reasoner": default_reasoner_model,
                }
            )
            _persist_user_prefs()
            st.success("✅ 已根据模型提供方自动切换 Base URL / Chat / Reasoner 模型")
            st.rerun()

        api_key = st.text_input(
            "API Key",
            value=st.session_state.user_prefs.get("ai_api_key", ""),
            type="password",
            placeholder="sk-...",
            help="仅保存在本地 data/user_prefs.json，不会写入代码仓库。",
        )
        base_url = st.text_input(
            "Base URL",
            value=st.session_state.user_prefs.get("ai_base_url", "") or default_base_url,
            placeholder=default_base_url,
        )

        col_model1, col_model2 = st.columns(2)
        with col_model1:
            model_chat = st.text_input(
                "Chat 模型",
                value=st.session_state.user_prefs.get("ai_model_chat", "") or default_chat_model,
            )
        with col_model2:
            model_reasoner = st.text_input(
                "Reasoner 模型",
                value=st.session_state.user_prefs.get("ai_model_reasoner", "") or default_reasoner_model,
            )

        next_ai_prefs = {
            "ai_provider": selected_provider,
            "ai_api_key": api_key.strip(),
            "ai_base_url": base_url.strip(),
            "ai_model_chat": model_chat.strip(),
            "ai_model_reasoner": model_reasoner.strip(),
        }
        changed = any(st.session_state.user_prefs.get(k, "") != v for k, v in next_ai_prefs.items())
        if changed:
            st.session_state.user_prefs.update(next_ai_prefs)
            _persist_user_prefs()
            st.success("✅ AI 模型设置已保存")

    st.divider()

    # 系统信息
    with st.container(border=True):
        st.markdown("### ℹ️ 系统信息")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("当前身份", st.session_state.user_prefs.get("user_role", "未设置"))
        with col2:
            st.metric("学习领域", st.session_state.user_prefs.get("user_field", "未设置"))

        col3, col4 = st.columns(2)
        with col3:
            st.metric("每日目标", f"{st.session_state.user_prefs.get('daily_limit', 5)} 题")
        with col4:
            st.metric("缓存题目数", question_cache.get_cache_count())

