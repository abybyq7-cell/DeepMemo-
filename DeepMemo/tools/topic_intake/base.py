from pathlib import Path
from typing import Optional


def load_prompt(prompt_path: Path, fallback: str) -> str:
    try:
        content = prompt_path.read_text(encoding="utf-8").strip()
        return content or fallback
    except Exception:
        return fallback


def safe_confidence(value: object, default: float = 0.6) -> float:
    try:
        conf = float(value)
    except Exception:
        conf = default
    return max(0.0, min(1.0, conf))


def detect_language(user_input: str, language: Optional[str] = None) -> str:
    import re

    if language and str(language).strip():
        lang = str(language).strip().lower()
        return "zh-CN" if lang.startswith("zh") else "en"
    return "zh-CN" if re.search(r"[\u4e00-\u9fff]", user_input or "") else "en"


def canonicalize_topic_text(topic: str) -> str:
    raw = (topic or "").strip()
    lowered = raw.lower()
    alias_map = {
        "线代": "线性代数",
        "高数极限": "高等数学中的极限",
        "tcp三次握手": "TCP 三次握手",
        "tcp 3次握手": "TCP 三次握手",
        "tcp3次握手": "TCP 三次握手",
    }
    return alias_map.get(lowered, raw)


def extract_path_from_framework(framework: dict, topic_type: str) -> list[str]:
    if topic_type == "subject":
        chapters = framework.get("chapters", []) if isinstance(framework, dict) else []
        return [str(c.get("title", "")).strip() for c in chapters if isinstance(c, dict) and str(c.get("title", "")).strip()]

    modules = framework.get("modules", []) if isinstance(framework, dict) else []
    return [str(m.get("title", "")).strip() for m in modules if isinstance(m, dict) and str(m.get("title", "")).strip()]
