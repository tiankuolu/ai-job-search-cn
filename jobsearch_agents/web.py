import asyncio
import hashlib
import json
import shutil
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .actions.analyze import _job_files, run_analyze
from .actions.apply import run_apply
from .actions.common import ActionContext, REPO_ROOT, RUNS_DIR, default_context
from .actions.interview import run_interview
from .actions.rank import run_rank
from .config import LLMConfig
from .runtime import OpenAICompatClient
from .runtime.trace import Trace

TERMINAL = {"completed", "failed", "review_required", "interrupted", "recorded"}
DOCUMENTS = {
    "evaluation": ("岗位评估", ".md"),
    "application": ("申请材料", "-application.md"),
    "research": ("公司调研", "-research.md"),
    "interview": ("面试准备", "-interview-prep.md"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


def job_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:20]


def documents(ctx: ActionContext, path: Path) -> list[dict]:
    result = []
    for kind, (label, suffix) in DOCUMENTS.items():
        document = ctx.evaluated_dir / f"{ctx.job_key(path)}{suffix}"
        if document.is_file():
            result.append({"kind": kind, "label": label, "name": document.name,
                           "content": document.read_text(encoding="utf-8")})
    return result


class RunRequest(BaseModel):
    action: Literal["analyze", "apply", "rank", "interview"]
    job_ids: list[str] = Field(default_factory=list)
    max_workers: int = Field(default=4, ge=1, le=8)


class RunStore:
    def __init__(self, root: Path, ctx: ActionContext) -> None:
        self.root = root
        self.ctx = ctx
        self.web_root = root / "web"
        self.web_root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.records: dict[str, dict] = {}
        self.traces: dict[str, Trace] = {}
        self.events: dict[str, list[dict]] = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobsearch-web")
        for path in self.web_root.glob("*/manifest.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            run_id = record["run_id"]
            self.records[run_id] = record
            event_path = path.parent / "events.jsonl"
            self.events[run_id] = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()] if event_path.is_file() else []
            if record["status"] not in TERMINAL:
                record.update(status="interrupted", ended_at=now(), error="服务已重新启动，原任务执行已中断。")
                self.append({"seq": len(self.events[run_id]) + 1, "type": "run.interrupted",
                             "timestamp": now(), "run_id": run_id, "data": {"error": record["error"]}})
                write_json(path, record)

    def append(self, event: dict) -> None:
        with self.lock:
            run_id = event["run_id"]
            with (self.web_root / run_id / "events.jsonl").open("a", encoding="utf-8") as output:
                output.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.events[run_id].append(event)

    def persist(self, run_id: str) -> None:
        write_json(self.web_root / run_id / "manifest.json", self.records[run_id])

    def submit(self, request: RunRequest, paths: list[Path]) -> dict:
        config = LLMConfig().require()
        self.ctx.read_profile()
        client = OpenAICompatClient(config)
        with self.lock:
            if any(record["status"] not in TERMINAL for record in self.records.values()):
                raise HTTPException(409, "已有任务正在执行，请等待任务结束。")
            trace = Trace(self.root, request.action, event_sink=self.append)
            run_id = trace.run_id
            (self.web_root / run_id).mkdir()
            self.traces[run_id] = trace
            self.events[run_id] = []
            self.records[run_id] = {
                "run_id": run_id, "action": request.action, "status": "queued", "source": "web",
                "created_at": now(), "ended_at": None, "error": None,
                "jobs": [{"id": job_id(path), "key": self.ctx.job_key(path)} for path in paths],
                "model": client.model, "artifacts": [], "result": None,
            }
            self.persist(run_id)
        trace.emit("run.queued", action=request.action, jobs=self.records[run_id]["jobs"])
        future = self.executor.submit(self.execute, request, paths, client, trace)
        future.add_done_callback(lambda finished: self.complete(run_id, finished))
        return self.summary(run_id)

    def execute(self, request: RunRequest, paths: list[Path], client: OpenAICompatClient, trace: Trace) -> dict:
        with self.lock:
            self.records[trace.run_id]["status"] = "running"
            self.persist(trace.run_id)
        trace.emit("run.started", action=request.action)
        if request.action == "analyze":
            result = run_analyze(client, self.ctx, max_workers=request.max_workers, job_files=paths, trace=trace)
            outputs = [self.ctx.evaluation_path(path) for path in paths]
        elif request.action == "apply":
            result = run_apply(client, self.ctx, paths[0], trace=trace)
            outputs = [self.ctx.repo_root / result["output_file"]]
        elif request.action == "interview":
            result = run_interview(client, self.ctx, paths[0], trace=trace)
            outputs = [self.ctx.repo_root / result["output_file"]]
        else:
            result = run_rank(client, self.ctx, trace=trace)
            outputs = [self.ctx.repo_root / result["output_file"]]
        result.pop("trace_obj", None)
        artifact_dir = self.web_root / trace.run_id / "artifacts"
        artifact_dir.mkdir()
        artifacts = []
        for output in outputs:
            target = artifact_dir / output.name
            shutil.copy2(output, target)
            artifacts.append({"name": target.name, "content": target.read_text(encoding="utf-8")})
            trace.emit("artifact.saved", name=target.name)
        return {"result": result, "artifacts": artifacts}

    def complete(self, run_id: str, future: Future) -> None:
        trace = self.traces[run_id]
        error = future.exception()
        with self.lock:
            record = self.records[run_id]
            if error is not None:
                status = "failed"
                record["error"] = f"{type(error).__name__}: {error}"
            else:
                value = future.result()
                record.update(value)
                status = "review_required" if value["result"].get("passed_review") is False else "completed"
            message = record["error"]
        if error is not None:
            events = list(trace.events)
            finished_tools = {(event["data"].get("call_id"), event["data"].get("tool_id")) for event in events if event["type"] == "tool.finished"}
            finished_agents = {event["data"]["execution_id"] for event in events if event["type"] == "agent.finished"}
            for event in events:
                data = event["data"]
                if event["type"] == "tool.started" and (data.get("call_id"), data.get("tool_id")) not in finished_tools:
                    trace.emit("tool.failed", **data, error=message)
                if event["type"] == "agent.started" and data["execution_id"] not in finished_agents:
                    trace.emit("agent.failed", **data, error=message)
        trace.emit(f"run.{status}", status=status, error=message)
        trace.save()
        with self.lock:
            record.update(status=status, ended_at=now())
            self.persist(run_id)

    def legacy(self, run_id: str) -> dict:
        path = self.root / f"{run_id}.json"
        if not path.is_file():
            raise HTTPException(404, "运行记录不存在。")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("calls"), list) or "action" not in data:
            raise HTTPException(404, "该文件没有模型调用记录。")
        return data

    def summary(self, run_id: str) -> dict:
        with self.lock:
            if run_id in self.records:
                record = {key: value for key, value in self.records[run_id].items() if key not in {"artifacts", "result"}}
                record["event_count"] = len(self.events[run_id])
                return record
        data = self.legacy(run_id)
        return {"run_id": run_id, "action": data["action"], "status": "recorded", "source": "trace" if data.get("events") else "legacy",
                "created_at": datetime.fromtimestamp((self.root / f"{run_id}.json").stat().st_mtime, timezone.utc).isoformat(),
                "ended_at": None, "error": None, "jobs": [], "event_count": len(data.get("events", [])),
                "model": data["calls"][0]["model"] if data["calls"] else None}

    def detail(self, run_id: str) -> dict:
        with self.lock:
            record = self.records.get(run_id)
            if record is None:
                return {**self.summary(run_id), "trace": self.legacy(run_id), "artifacts": [], "result": None}
            result = dict(record)
            events = list(self.events[run_id])
            trace = self.traces.get(run_id)
        trace_path = self.root / f"{run_id}.json"
        data = trace.to_dict() if trace is not None else json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.is_file() else {"calls": [], "total_tokens": 0}
        data["events"] = events
        return {**result, "trace": data}

    def list_runs(self) -> list[dict]:
        with self.lock:
            ids = set(self.records)
        for path in self.root.glob("*.json"):
            if path.stem in ids:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("calls"), list) and "action" in data:
                ids.add(path.stem)
        return sorted((self.summary(run_id) for run_id in ids), key=lambda item: item["created_at"], reverse=True)


def create_app(ctx: ActionContext | None = None, runs_dir: Path | None = None) -> FastAPI:
    context = ctx or default_context()
    store = RunStore(runs_dir or RUNS_DIR, context)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        store.executor.shutdown(wait=True)

    app = FastAPI(title="求职 Agent 工作台", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "仅接受本机页面发起的任务。"}, status_code=403)
        return await call_next(request)

    def jobs_by_id() -> dict[str, Path]:
        return {job_id(path): path for path in _job_files(context)}

    def resolve_run(run_id: str) -> str:
        if not run_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in run_id):
            raise HTTPException(404, "运行标识无效。")
        return run_id

    @app.get("/api/meta")
    def meta():
        config = LLMConfig()
        missing = [key for key, value in {"JOBSEARCH_LLM_BASE_URL": config.base_url, "JOBSEARCH_LLM_MODEL": config.model, "JOBSEARCH_LLM_API_KEY": config.api_key}.items() if not value]
        return {"model": config.model, "configured": not missing, "missing": missing,
                "workspace": str(context.data_root), "actions": ["analyze", "apply", "rank", "interview"]}

    @app.get("/api/jobs")
    def list_jobs():
        return [{"id": key, "key": context.job_key(path), "title": context.job_key(path),
                 "documents": [doc["kind"] for doc in documents(context, path)]} for key, path in jobs_by_id().items()]

    @app.get("/api/jobs/{identifier}")
    def get_job(identifier: str):
        path = jobs_by_id().get(identifier)
        if path is None:
            raise HTTPException(404, "岗位不存在。")
        return {"id": identifier, "key": context.job_key(path), "content": path.read_text(encoding="utf-8-sig"),
                "documents": documents(context, path)}

    @app.get("/api/runs")
    def list_runs():
        return store.list_runs()

    @app.post("/api/runs", status_code=202)
    def start_run(body: RunRequest):
        known = jobs_by_id()
        if len(set(body.job_ids)) != len(body.job_ids):
            raise HTTPException(422, "岗位选择存在重复。")
        if any(key not in known for key in body.job_ids):
            raise HTTPException(404, "选中的岗位不存在。")
        paths = [known[key] for key in body.job_ids]
        if body.action == "analyze" and not paths:
            raise HTTPException(422, "请选择需要分析的岗位。")
        if body.action in {"apply", "interview"} and len(paths) != 1:
            raise HTTPException(422, "该任务需要选择一个岗位。")
        config = LLMConfig()
        if not all((config.base_url, config.model, config.api_key)):
            raise HTTPException(503, "模型配置缺失，请设置 JOBSEARCH_LLM_BASE_URL、JOBSEARCH_LLM_MODEL 和 JOBSEARCH_LLM_API_KEY 后重新启动服务。")
        if body.action == "rank" and not any(context.evaluation_path(path).is_file() for path in known.values()):
            raise HTTPException(422, "当前没有评估报告，请先完成岗位分析。")
        return store.submit(body, paths)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return store.detail(resolve_run(run_id))

    @app.get("/api/runs/{run_id}/events")
    async def stream_events(run_id: str, request: Request, after: int = Query(0, ge=0), last_event_id: int | None = Header(None, ge=0)):
        resolve_run(run_id)
        detail = store.detail(run_id)
        cursor = max(after, last_event_id or 0)

        async def stream():
            nonlocal cursor
            heartbeat = 0
            while not await request.is_disconnected():
                with store.lock:
                    events = list(store.events.get(run_id, detail["trace"].get("events", [])))
                    status = store.records.get(run_id, detail)["status"]
                for event in events:
                    if event["seq"] > cursor:
                        yield f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                        cursor = event["seq"]
                if status in TERMINAL and (not events or cursor >= events[-1]["seq"]):
                    yield "event: end\ndata: {}\n\n"
                    return
                heartbeat += 1
                if heartbeat % 30 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.35)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    dist = REPO_ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8765)
