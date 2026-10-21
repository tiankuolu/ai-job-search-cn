# setup 动作：单次 LLM 调用把简历文本转换为资料文件格式（GOAL.md §2.3，不做成 agent）。

import re
from pathlib import Path

from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, PROFILE_DIR, RUNS_DIR

SETUP_PROMPT = (
    "你是资料格式转换器。给你一份简历原文与三个资料文件模板，"
    "你把简历内容如实填进模板结构，输出三个文件的完整内容。规则：\n"
    "1. 简历里没有的字段保持模板空位，禁止编造或推断。\n"
    "2. 证据文件 evidence.md 里只填简历中可验证的成果，每条注明证据来源。\n"
    "3. 输出格式：三个文件内容依次输出，每个文件前一行写"
    " <<<FILE:文件名>>> 作为分隔标记。\n"
)


def run_setup(
    client: LLMClient, ctx: ActionContext, resume_text: str
) -> dict:
    """把简历文本转换为 candidate/preferences/evidence 三个资料文件并写入 profile 目录。"""
    templates = {}
    for name in ("candidate.md", "preferences.md", "evidence.md"):
        path = Path(ctx.repo_root) / "markets" / "china" / "profile" / name
        templates[name] = path.read_text(encoding="utf-8")

    trace = Trace(RUNS_DIR, "setup")
    agent = Agent(
        name="setup",
        system_prompt=SETUP_PROMPT,
        client=client,
        trace=trace,
    )
    raw = agent.run(
        f"# 简历原文\n{resume_text}\n\n# 模板\n"
        + "\n".join(
            f"## {name}\n{content}" for name, content in templates.items()
        )
    )

    target_dir = ctx.profile_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    sections = {}
    current = None
    for line in raw.splitlines():
        match = re.match(r"^<<<FILE:(\S+?)>>>$", line.strip())
        if match:
            current = match.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    for name in ("candidate.md", "preferences.md", "evidence.md"):
        if name not in sections:
            raise ValueError(f"模型输出里缺少 <<<FILE:{name}>>> 分隔标记")

    written = []
    for name, lines in sections.items():
        out = target_dir / name
        out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        written.append(str(out.relative_to(ctx.repo_root)))

    trace.save()
    return {
        "written": written,
        "profile_dir": str(target_dir.relative_to(ctx.repo_root)),
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
