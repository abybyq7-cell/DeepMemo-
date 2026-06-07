"""Project-wide configuration values and helpers."""

import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if isinstance(value, str) and value.strip() else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

# ============================================================================
# AI 模型配置
# ============================================================================
MODEL_CHAT = _env_str("DEEPSEEK_MODEL_CHAT", "deepseek-chat")
MODEL_REASONER = _env_str("DEEPSEEK_MODEL_REASONER", "deepseek-reasoner")
BASE_URL = _env_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ============================================================================
# API 配置
# ============================================================================
# 从环境变量读取 API Key，避免将密钥硬编码在仓库中。
# 请在运行环境中设置 `DEEPSEEK_API_KEY`。
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BACKEND_URL = _env_str("DEEPMEMO_API_BACKEND_URL", "http://localhost:8000")

# ============================================================================
# 文件和路径
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_FILE = Path(_env_str("DEEPMEMO_CACHE_FILE", str(DATA_DIR / "question_cache.json")))
DATABASE_FILE = Path(_env_str("DEEPMEMO_DB_FILE", str(DATA_DIR / "deep_memo.db")))

# ============================================================================
# 学习配置
# ============================================================================
DAILY_LIMIT = _env_int("DEEPMEMO_DAILY_LIMIT", 5)
QUESTIONS_PER_BATCH = _env_int("DEEPMEMO_QUESTIONS_PER_BATCH", 15)
MIN_CACHE_THRESHOLD = _env_int("DEEPMEMO_MIN_CACHE_THRESHOLD", 2)
QUESTIONS_PER_TOPIC = _env_int("DEEPMEMO_QUESTIONS_PER_TOPIC", 3)

# ============================================================================
# 难度级别
# ============================================================================
DIFFICULTY_LEVELS = ["easy", "standard", "hard"]
DIFFICULTY_DISTRIBUTION = {
    "easy": 0.33,      # 33% 简单题
    "standard": 0.34,  # 34% 标准题
    "hard": 0.33       # 33% 困难题
}

# ============================================================================
# UI 颜色系统（Apple 设计）
# ============================================================================
COLORS = {
    # 主色
    "primary": "#0071e3",        # Apple Blue
    "secondary": "#555555",      # Gray
    
    # 背景
    "background": "#f5f5f7",     # Apple Light Gray
    "surface": "#ffffff",        # White
    "surface_variant": "#f8f8f8",# Light variant
    
    # 文字
    "text_primary": "#1d1d1f",   # Apple Black
    "text_secondary": "#555555", # Medium Gray
    "text_tertiary": "#86868b",  # Light Gray
    
    # 状态
    "success": "#34c759",        # Apple Green
    "warning": "#ff9500",        # Apple Orange
    "error": "#ff3b30",          # Apple Red
    "info": "#0071e3",           # Apple Blue
    
    # 边界
    "border": "#d2d2d7",         # Apple Border Gray
}

# ============================================================================
# UI 尺寸（圆角、间距、阴影）
# ============================================================================
BORDER_RADIUS = {
    "xs": "4px",       # 进度条
    "sm": "8px",       # 单选框
    "md": "12px",      # 按钮
    "lg": "18px",      # 卡片
    "xl": "24px",      # 大容器
}

SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "20px",
    "2xl": "24px",
}

SHADOW = {
    "sm": "0 2px 4px rgba(0,0,0,0.05)",
    "md": "0 4px 12px rgba(0,0,0,0.08)",
    "lg": "0 8px 24px rgba(0,0,0,0.12)",
}

# ============================================================================
# 文本和标签
# ============================================================================
LABELS = {
    "app_title": "学习",
    "menu_study": "刷题",
    "menu_notes": "笔记",
    "menu_mistakes": "错题",
    "menu_library": "知识库",
    "menu_settings": "设置",
    
    "btn_submit": "提交答案",
    "btn_next": "下一题",
    "btn_retry": "重新作答",
    "btn_skip": "跳过",
    
    "msg_correct": "回答正确",
    "msg_incorrect": "答案不正确",
    "msg_generating": "生成题目中...",
    "msg_loading": "加载中...",
    
    "review_mode": "复习模式",
    "study_mode": "学习模式",
}

# ============================================================================
# 日志配置
# ============================================================================
LOG_LEVEL = _env_str("DEEPMEMO_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

# ============================================================================
# 环境判断
# ============================================================================
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "development") == "development"
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

# ============================================================================
# 用户默认偏好
# ============================================================================
DEFAULT_USER_PREFS = {
    'daily_limit': DAILY_LIMIT,
    'daily_questions_per_topic': QUESTIONS_PER_TOPIC,
    'user_role': '学生',
    'user_field': '通识教育',
    'learning_style': '苏格拉底 (引导者)',
    'language': 'zh',
    'selected_topics': [],
    'ai_provider': 'deepseek',
    'ai_api_key': '',
    'ai_base_url': '',
    'ai_model_chat': MODEL_CHAT,
    'ai_model_reasoner': MODEL_REASONER,
}

# ============================================================================
# 验证和工具函数
# ============================================================================

def get_cache_file() -> Path:
    """获取缓存文件路径"""
    return CACHE_FILE

def ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def ensure_data_dir() -> None:
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_config_summary() -> dict:
    """获取配置摘要（用于调试）"""
    return {
        "model_chat": MODEL_CHAT,
        "model_reasoner": MODEL_REASONER,
        "cache_file": str(CACHE_FILE),
        "database_file": str(DATABASE_FILE),
        "api_backend_url": API_BACKEND_URL,
        "daily_limit": DAILY_LIMIT,
        "questions_per_batch": QUESTIONS_PER_BATCH,
        "environment": "production" if IS_PRODUCTION else "development",
        "api_key_set": bool(API_KEY),
    }
