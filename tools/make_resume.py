import argparse
import json
from pathlib import Path

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.config import LLMConfig
from jobsearch_agents.delivery.resume import ResumePlan, render_resume
from jobsearch_agents.delivery.generation import generate_resume
from jobsearch_agents.runtime import OpenAICompatClient
from jobsearch_agents.runtime.trace import Trace


def report_progress(event: dict):
    data = event["data"]
    if event["type"] == "llm.started":
        print(f"模型调用开始：{data['agent']}", flush=True)
    elif event["type"] == "llm.finished":
        print(f"模型调用完成：{data['agent']}，耗时 {data['latency_ms'] / 1000:.1f} 秒", flush=True)
    elif event["type"] in {"review.finished", "resume.review"}:
        print(f"第 {data['round']} 轮审查：{'通过' if data['pass'] else '需要修改'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="使用 ASu 方法提升简历并制作可编辑 HTML 与单页 PDF")
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--application", type=Path)
    parser.add_argument("--render-plan", type=Path, help="重新排版已经审查的结构化正文")
    parser.add_argument("--browser-channel", default="msedge", choices=["msedge", "chrome", "chromium"])
    args = parser.parse_args()
    job = args.job.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"输出目录已经存在：{output}")
    tools = {"browser_channel": args.browser_channel}
    if args.render_plan:
        plan = ResumePlan.model_validate_json(args.render_plan.read_text(encoding="utf-8"))
        result = render_resume(plan, output, tools)
    else:
        ctx = default_context()
        client = OpenAICompatClient(LLMConfig())
        trace = Trace(RUNS_DIR, "asu-resume", event_sink=report_progress)
        try:
            print("正在使用真实模型完成岗位定位、项目改写和证据审查", flush=True)
            analysis = {"saved_application": args.application.read_text(encoding="utf-8")} if args.application else {}
            result = generate_resume(client, ctx, job.read_text(encoding="utf-8"), output, tools, trace,
                                     progress=lambda message: print(message, flush=True), analysis=analysis)
            result["trace"] = str(trace.save())
        finally:
            trace.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
