# analyze 动作：主控 agent 用 spawn 工具把每个岗位派发给分析 agent 并行扇出。

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient, ToolRegistry, make_spawn_tool
from ..runtime.trace import Trace
from ..tools_wrap.file_tools import register_file_tools
from ..tools_wrap.key_tools import register_key_tools
from .common import ActionContext, EVALUATED_DIR, INBOX_DIR, REPO_ROOT, RUNS_DIR


def _analyst_factory(client: LLMClient, ctx: ActionContext, trace: Trace):
    """每个子任务创建一个配好工具的分析 agent。"""

    def factory(task: str) -> Agent:
        tools = ToolRegistry()
        # job_key 是仓库自带的确定性工具，与运行工作区无关，固定从包自身仓库加载
        register_key_tools(tools, REPO_ROOT)
        register_file_tools(tools, ctx.repo_root)
        return Agent(
            name="analyzer",
            system_prompt=load_prompt("analyzer"),
            client=client,
            tools=tools,
            trace=trace,
        )

    return factory


def _orchestrator(client: LLMClient, ctx: ActionContext, trace: Trace) -> Agent:
    """主控 agent：只做一件事——为每个岗位文件调用一次 spawn。"""
    tools = ToolRegistry()
    tools.register(make_spawn_tool(_analyst_factory(client, ctx, trace), trace))
    system_prompt = (
        "你是岗位分析主控 agent。给你一份岗位文件路径与候选人资料目录，"
        "你的职责是：对列表里的每个岗位文件调用一次 spawn 工具，"
        "task 里必须包含：完整的岗位文件路径（让分析 agent 自己用 read_file 读取）、"
        "候选人资料的三个文件路径、以及把评估报告用 write_file 写入的目标路径"
        "（markets/china/jobs/evaluated/ 下，文件名与输入同名）。"
        "全部岗位派出并收到结果后，输出一行总结：处理了几个、成功几个、各自输出路径。"
        "禁止自己做分析，禁止跳过任何一个岗位。"
    )
    return Agent(
        name="analyze-orchestrator",
        system_prompt=system_prompt,
        client=client,
        tools=tools,
        max_turns=32,
        trace=trace,
    )


def _job_files() -> list[Path]:
    if not INBOX_DIR.is_dir():
        raise FileNotFoundError(f"目录不存在：{INBOX_DIR}")
    files = sorted(p for p in INBOX_DIR.glob("*.md") if p.is_file())
    return files


def _subtasks(ctx: ActionContext, files: list[Path]) -> list[str]:
    EVALUATED_DIR.mkdir(parents=True, exist_ok=True)
    profile = ctx.read_profile()
    profile_note = (
        f"候选人资料：candidate.md 见 {ctx.profile_dir / 'candidate.md'}，"
        f"preferences.md 见 {ctx.profile_dir / 'preferences.md'}，"
        f"evidence.md 见 {ctx.profile_dir / 'evidence.md'}"
        f"（全部用 read_file 读取，相对路径写法：{(ctx.profile_dir / 'candidate.md').relative_to(ctx.repo_root).as_posix()}）。"
    )
    tasks = []
    for job_file in files:
        rel = job_file.relative_to(ctx.repo_root).as_posix()
        out_rel = (
            job_file.relative_to(ctx.repo_root).as_posix().replace("/inbox/", "/evaluated/")
        )
        tasks.append(
            f"分析岗位文件 {rel}（用 read_file 读取全文），"
            f"并读取候选人资料（{profile_note}）。"
            f"按你的 system prompt 输出评估报告，"
            f"用 write_file 写入 {out_rel}，然后结束。"
        )
    return tasks


def run_analyze(client: LLMClient, ctx: ActionContext, max_workers: int = 4) -> dict:
    """并行扇出全部 inbox 岗位，返回每个岗位的处理结果与 trace 路径。"""
    files = _job_files()
    if not files:
        raise FileNotFoundError(f"{INBOX_DIR} 下没有任何 .md 岗位文件")

    trace = Trace(RUNS_DIR, "analyze")
    factory = _analyst_factory(client, ctx, trace)

    def analyze_one(task: str) -> dict:
        analyst = factory(task)
        try:
            output = analyst.run(task)
            return {"status": "done", "output": output}
        except Exception as exc:
            return {"status": "error", "error": repr(exc)}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(analyze_one, _subtasks(ctx, files)))

    trace.save()
    return {
        "jobs": [
            {"file": f.relative_to(ctx.repo_root).as_posix(), **r}
            for f, r in zip(files, results)
        ],
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
