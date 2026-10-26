# 从本目录读取 Markdown 文件作为模型提示词。

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

KNOWN_PROMPTS = ["analyzer", "writer", "reviewer", "ranker", "judge", "interview", "researcher"]


def load_prompt(name: str) -> str:
    """按名字加载 prompt 文件，name 不在已知清单内即崩溃。"""
    if name not in KNOWN_PROMPTS:
        raise ValueError(f"未知的 prompt 名：{name}，已知：{KNOWN_PROMPTS}")
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt 文件缺失：{path}")
    return path.read_text(encoding="utf-8")
