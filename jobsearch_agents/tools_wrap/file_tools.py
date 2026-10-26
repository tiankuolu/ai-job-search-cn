# 文件读写工具：agent 在限定工作区内读取岗位、资料与写入产物。
# 路径必须在根目录内（resolve 后校验），越界就地崩溃，防止 agent 读写任意位置。

from pathlib import Path

from ..runtime.tools import Tool, ToolRegistry


def _resolve_within(repo_root: Path, relative: str) -> Path:
    target = (repo_root / relative).resolve()
    root = repo_root.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"路径越界：{relative} 不在 {root} 内")
    return target


def register_file_tools(registry: ToolRegistry, repo_root: Path) -> None:
    def read_file(path: str) -> str:
        target = _resolve_within(repo_root, path)
        if not target.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")
        return target.read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        target = _resolve_within(repo_root, path)
        if not target.parent.exists():
            raise FileNotFoundError(f"目录不存在，拒绝创建目录：{path}")
        target.write_text(content, encoding="utf-8")
        return f"written: {path} ({len(content)} chars)"

    def list_dir(path: str) -> str:
        target = _resolve_within(repo_root, path)
        if not target.is_dir():
            raise FileNotFoundError(f"目录不存在：{path}")
        entries = sorted(
            p.relative_to(repo_root).as_posix() + ("/" if p.is_dir() else "")
            for p in target.iterdir()
        )
        return "\n".join(entries) if entries else "(empty)"

    registry.register(
        Tool(
            name="read_file",
            description="读取工作区内一个文本文件的内容（UTF-8）。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "工作区相对路径"}},
                "required": ["path"],
            },
            func=read_file,
        )
    )
    registry.register(
        Tool(
            name="write_file",
            description="把文本内容写入工作区内一个已存在目录下的文件（覆盖写入）。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "工作区相对路径"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
            func=write_file,
        )
    )
    registry.register(
        Tool(
            name="list_dir",
            description="列出一个目录下的直接子项。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "工作区相对路径"}},
                "required": ["path"],
            },
            func=list_dir,
        )
    )
