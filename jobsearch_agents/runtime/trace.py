# Trace 记录每次模型调用的输入输出、工具调用、token 与耗时。

import json
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable


@dataclass
class LLMCallRecord:
    """一次 LLM 调用的完整记录。"""

    call_id: str
    agent: str
    model: str
    messages: list
    response: dict | None = None
    tool_calls: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error: str | None = None
    execution_id: str | None = None
    task_id: str | None = None


class Trace:
    """一个运行周期（一次 action 或一轮自改）的 trace 容器。"""

    def __init__(
        self, run_dir: Path, action: str,
        event_sink: Callable[[dict], None] | None = None,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.action = action
        self.run_id = f"{action}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.records: list[LLMCallRecord] = []
        self._total_prompt = 0
        self._total_completion = 0
        self.events: list[dict] = []
        self._lock = RLock()
        self._event_sink = event_sink

    def emit(self, event_type: str, **data) -> None:
        with self._lock:
            event = {
                "seq": len(self.events) + 1,
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id,
                "data": deepcopy(data),
            }
            self.events.append(event)
            if self._event_sink is not None:
                self._event_sink(event)

    def new_call(
        self, agent: str, model: str, messages: list,
        execution_id: str | None = None, task_id: str | None = None,
    ) -> LLMCallRecord:
        record = LLMCallRecord(
            call_id=uuid.uuid4().hex[:12],
            agent=agent,
            model=model,
            messages=deepcopy(messages),
            execution_id=execution_id,
            task_id=task_id,
        )
        with self._lock:
            self.records.append(record)
            self.emit("llm.started", **vars(record))
            if self._event_sink is not None:
                self.save()
        return record

    def finish_call(self, record: LLMCallRecord, started: float) -> None:
        with self._lock:
            record.latency_ms = int((time.time() - started) * 1000)
            self._total_prompt += record.prompt_tokens
            self._total_completion += record.completion_tokens
            self.emit("llm.failed" if record.error else "llm.finished", **vars(record))
            if self._event_sink is not None:
                self.save()

    @property
    def total_tokens(self) -> int:
        return self._total_prompt + self._total_completion

    def to_dict(self) -> dict:
        with self._lock:
            return deepcopy({
                "run_id": self.run_id,
                "action": self.action,
                "calls": [vars(r) for r in self.records],
                "events": self.events,
                "total_prompt_tokens": self._total_prompt,
                "total_completion_tokens": self._total_completion,
                "total_tokens": self.total_tokens,
            })

    def save(self) -> Path:
        path = self.run_dir / f"{self.run_id}.json"
        with self._lock:
            pending = path.with_suffix(".pending")
            pending.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            pending.replace(path)
        return path

    def assert_complete(self) -> None:
        """验收 A8 的判定逻辑：存在调用记录且回填完整。"""
        if not self.records:
            raise AssertionError("trace 里没有任何 LLM 调用记录")
        for record in self.records:
            if record.response is None and record.error is None:
                raise AssertionError(
                    f"调用 {record.call_id}（agent={record.agent}）既没有响应也没有错误记录"
                )
            if record.latency_ms < 0:
                raise AssertionError(
                    f"调用 {record.call_id}（agent={record.agent}）没有耗时记录"
                )
