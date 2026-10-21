# Trace 记录：每次 LLM 调用的输入输出、工具调用、token、耗时全部落盘（GOAL.md A8）。

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


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


class Trace:
    """一个运行周期（一次 action 或一轮自改）的 trace 容器。"""

    def __init__(self, run_dir: Path, action: str) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.action = action
        self.run_id = f"{action}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.records: list[LLMCallRecord] = []
        self._total_prompt = 0
        self._total_completion = 0

    def new_call(self, agent: str, model: str, messages: list) -> LLMCallRecord:
        record = LLMCallRecord(
            call_id=uuid.uuid4().hex[:12],
            agent=agent,
            model=model,
            messages=messages,
        )
        self.records.append(record)
        return record

    def finish_call(self, record: LLMCallRecord, started: float) -> None:
        record.latency_ms = int((time.time() - started) * 1000)
        self._total_prompt += record.prompt_tokens
        self._total_completion += record.completion_tokens

    @property
    def total_tokens(self) -> int:
        return self._total_prompt + self._total_completion

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "action": self.action,
            "calls": [vars(r) for r in self.records],
            "total_prompt_tokens": self._total_prompt,
            "total_completion_tokens": self._total_completion,
            "total_tokens": self.total_tokens,
        }

    def save(self) -> Path:
        path = self.run_dir / f"{self.run_id}.json"
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
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
