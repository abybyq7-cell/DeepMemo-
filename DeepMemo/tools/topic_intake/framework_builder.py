from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .base import detect_language, load_prompt


class FrameworkBuilderModule:
    FORBIDDEN_KEYS = {"definition", "key idea", "practical example"}
    VERSION = "1.0.0"
    INPUT_SCHEMA = {
        "normalized_topic": "str",
        "topic_type": "knowledge_point|subject|mixed|invalid",
        "scope_info": "Dict[str, Any]",
        "language": "Optional[str]",
    }
    OUTPUT_SCHEMA = {
        "framework": "Dict[str, Any]",
        "assumptions": "List[str]",
        "source": "model|fallback|memory",
        "version": "str",
    }

    def __init__(self, chat_json: Callable[..., Optional[Any]], model_reasoner: str) -> None:
        self._chat_json = chat_json
        self._model_reasoner = model_reasoner
        self._prompt_path = Path(__file__).resolve().parent / "prompts" / "framework_builder.prompt.md"

    def _contains_forbidden_keys(self, node: Any) -> bool:
        if isinstance(node, dict):
            for key, value in node.items():
                key_norm = str(key).strip().lower()
                if key_norm in self.FORBIDDEN_KEYS:
                    return True
                if self._contains_forbidden_keys(value):
                    return True
            return False
        if isinstance(node, list):
            return any(self._contains_forbidden_keys(item) for item in node)
        return False

    def _fallback(self, normalized_topic: str, topic_type: str, language: str) -> Dict[str, Any]:
        zh = language == "zh-CN"
        if topic_type == "subject":
            if zh:
                framework = {
                    "style": "textbook",
                    "chapters": [
                        {"title": "基础概念与记号", "sections": ["学科范围", "核心术语", "基本对象"]},
                        {"title": "基本理论与结构", "sections": ["基本法则", "关键命题", "结构性理解"]},
                        {"title": "标准方法与解题流程", "sections": ["常用方法", "典型题型", "步骤化求解"]},
                        {"title": "应用场景与综合训练", "sections": ["基础应用", "综合案例", "跨主题连接"]},
                        {"title": "进阶专题与拓展", "sections": ["高阶主题", "研究导向", "进一步阅读"]},
                    ],
                }
            else:
                framework = {
                    "style": "textbook",
                    "chapters": [
                        {"title": "Foundations and Notation", "sections": ["Scope of the subject", "Core terms", "Basic objects"]},
                        {"title": "Core Theory and Structure", "sections": ["Fundamental laws", "Key propositions", "Structural understanding"]},
                        {"title": "Standard Methods and Workflows", "sections": ["Canonical methods", "Typical problem types", "Step-by-step solving"]},
                        {"title": "Applications and Integrated Practice", "sections": ["Basic applications", "Integrated cases", "Cross-topic links"]},
                        {"title": "Advanced Topics and Extension", "sections": ["Advanced themes", "Research directions", "Further reading"]},
                    ],
                }
        else:
            if zh:
                framework = {
                    "style": "micro_curriculum",
                    "modules": [
                        {"title": "概念定义", "goal": f"准确说出 {normalized_topic} 的定义与适用边界"},
                        {"title": "直觉理解", "goal": "建立对核心思想的直觉模型"},
                        {"title": "前置知识", "goal": "补齐理解该知识点需要的基础"},
                        {"title": "核心机制", "goal": "掌握推理过程和关键步骤"},
                        {"title": "例题或应用", "goal": "在代表性题目/场景中正确使用"},
                        {"title": "常见错误", "goal": "识别并避免高频误区"},
                        {"title": "延伸主题", "goal": "建立与相关知识的迁移连接"},
                    ],
                }
            else:
                framework = {
                    "style": "micro_curriculum",
                    "modules": [
                        {"title": "Concept Definition", "goal": f"State the definition and boundary of {normalized_topic}"},
                        {"title": "Intuitive Understanding", "goal": "Build a practical mental model of the idea"},
                        {"title": "Prerequisite Knowledge", "goal": "Fill in minimum prerequisites before deep practice"},
                        {"title": "Core Mechanism", "goal": "Master the key mechanism and reasoning steps"},
                        {"title": "Examples or Applications", "goal": "Apply the concept on representative tasks"},
                        {"title": "Common Mistakes", "goal": "Identify and avoid high-frequency errors"},
                        {"title": "Extended Topics", "goal": "Connect this point to nearby advanced topics"},
                    ],
                }
        return {
            "framework": framework,
            "assumptions": ["Deterministic framework fallback used."],
            "source": "fallback",
            "version": self.VERSION,
        }

    def run(
        self,
        normalized_topic: str,
        topic_type: str,
        scope_info: Dict[str, Any],
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_topic_type = topic_type if topic_type in {"subject", "knowledge_point"} else "knowledge_point"
        lang = detect_language(normalized_topic, language)
        output_lang = "Chinese (Simplified)" if lang == "zh-CN" else "English"
        fallback = self._fallback(normalized_topic=normalized_topic, topic_type=safe_topic_type, language=lang)
        prompt = load_prompt(
            self._prompt_path,
            "You build a learning framework. Return JSON only.",
        )
        user_prompt = (
            f"Topic: {normalized_topic}\n"
            f"Topic type: {safe_topic_type}\n"
            f"Output language: {output_lang}\n"
            f"Domain: {scope_info.get('domain', '')}\n"
            f"Subject family: {scope_info.get('subject_family', '')}\n"
            f"Prerequisites: {scope_info.get('prerequisites', [])}"
        )
        parsed = self._chat_json(
            model=self._model_reasoner,
            system_prompt=prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1800,
        )
        if not isinstance(parsed, dict) or self._contains_forbidden_keys(parsed):
            return fallback

        if safe_topic_type == "subject":
            if str(parsed.get("style", "")).strip() != "textbook":
                return fallback
            chapters = parsed.get("chapters", [])
            if not isinstance(chapters, list) or not chapters:
                return fallback
            clean_chapters: List[Dict[str, Any]] = []
            for chapter in chapters:
                if not isinstance(chapter, dict):
                    continue
                title = str(chapter.get("title", "")).strip()
                if not title:
                    continue
                sections = chapter.get("sections", [])
                sections = [str(x).strip() for x in sections if str(x).strip()] if isinstance(sections, list) else []
                if len(sections) < 2:
                    continue
                clean_chapters.append({"title": title, "sections": sections[:5]})
            clean_chapters = clean_chapters[:8]
            if len(clean_chapters) < 4:
                return fallback
            return {
                "framework": {"style": "textbook", "chapters": clean_chapters},
                "assumptions": ["Model-based framework generation used."],
                "source": "model",
                "version": self.VERSION,
            }

        if str(parsed.get("style", "")).strip() != "micro_curriculum":
            return fallback
        modules = parsed.get("modules", [])
        if not isinstance(modules, list) or not modules:
            return fallback
        clean_modules: List[Dict[str, Any]] = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            title = str(module.get("title", "")).strip()
            goal = str(module.get("goal", "")).strip()
            if title and goal:
                clean_modules.append({"title": title, "goal": goal})
        if not clean_modules:
            return fallback
        return {
            "framework": {"style": "micro_curriculum", "modules": clean_modules[:8]},
            "assumptions": ["Model-based framework generation used."],
            "source": "model",
            "version": self.VERSION,
        }
