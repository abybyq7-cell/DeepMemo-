"""
UTF-8 编码初始化 - 必须在所有其他导入前执行
"""
import sys
import os
import io

# 强制所有输出使用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'

# 最后手段：重定向流
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# 🔧  修补 httpx 的编码方式为 UTF-8（关键修复！）
try:
    import httpx._models
    _original_normalize = httpx._models._normalize_header_value
    
    def _patched_normalize(value, encoding=None):
        """使用 UTF-8 而不是默认的 ASCII"""
        if encoding is None:
            encoding = 'utf-8'  # 从 ascii 改为 utf-8
        return _original_normalize(value, encoding)
    
    httpx._models._normalize_header_value = _patched_normalize
except Exception:
    pass