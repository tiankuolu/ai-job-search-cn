# Agent 循环：请求 → 工具调用解析 → 执行 → 回填 → 终止判定（GOAL.md §2.1）。
# 模型客户端是一个可替换的协议对象：OpenAI 兼容端点与单元层的假模型走同一接口。

import json
import time
from typing import Any, Protocol

from ..config import LLMConfig
from .tools import ToolRegistry, ToolResult
from .trace import Trace, LLMCallRecord


class LLMClient(Protocol):
    """运行时依赖的最小模型接口。真实实现与假模型都满足这个协议。"""

    model: str

    def chat(self, messages: list, tools: list) -> dict:
        """返回 OpenAI 兼容格式的单次响应字典。"""
        ...


class OpenAICompatClient:
    """真实模型客户端：所有 OpenAI 兼容端点（DeepSeek/Qwen/GLM/Ollama）共用的实现。"""

    def __init__(self, config: LLMConfig) -> None:
        import os

        import httpx  # 直接 import，缺依赖就地崩溃
        from openai import OpenAI

        config.require()
        self.model = str(config.model)
        # 超时可配置：本地 CPU 推理的端点单次生成可能超过默认 180 秒
        timeout_seconds = float(os.environ.get("JOBSEARCH_LLM_TIMEOUT", "180"))
        # Windows 系统代理（注册表级）会把 localhost 请求劫持到代理软件再返回 502，
        # 本地端点必须绕过系统代理；云端端点保持默认（尊重用户代理配置）。
        base = str(config.base_url)
        http_client = None
        if "://localhost" in base or "://127.0.0.1" in base:
            http_client = httpx.Client(trust_env=False, timeout=timeout_seconds)
        self._client = OpenAI(
            base_url=base,
            api_key=config.api_key,
            timeout=timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )

    def chat(self, messages: list, tools: list) -> dict:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
        )
        return response.model_dump()


class Agent:
    """单个 agent：system prompt + 工具集 + 对话循环 + 终止保护。"""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        client: LLMClient,
        tools: ToolRegistry | None = None,
        max_turns: int = 12,
        trace: Trace | None = None,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.client = client
        self.tools = tools or ToolRegistry()
        self.max_turns = max_turns
        self.trace = trace

    def run(self, user_message: str) -> str:
        """执行一次完整循环，返回最终文本回复。"""
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        final_text = ""
        for turn in range(self.max_turns):
            record: LLMCallRecord | None = None
            started = time.time()
            if self.trace is not None:
                record = self.trace.new_call(
                    agent=self.name, model=self.client.model, messages=messages
                )
            try:
                response = self.client.chat(messages, self.tools.schemas())
            except Exception as exc:  # 网络/配额错误记录后原样抛出，fast-fail
                if record is not None:
                    record.error = repr(exc)
                    self.trace.finish_call(record, started)
                raise
            if record is not None:
                record.response = {
                    "content": response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content"),
                    "tool_calls": response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("tool_calls"),
                }
                usage = response.get("usage") or {}
                record.prompt_tokens = usage.get("prompt_tokens", 0)
                record.completion_tokens = usage.get("completion_tokens", 0)
                self.trace.finish_call(record, started)

            message = response["choices"][0]["message"]
            messages.append(message)
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                final_text = message.get("content") or ""
                return final_text

            for call in tool_calls:
                result = self._execute_tool_call(call, record)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": result,
                    }
                )
        raise RuntimeError(
            f"agent {self.name} 达到最大轮数 {self.max_turns} 仍未给出最终回复"
        )

    def _execute_tool_call(self, call: dict, record: LLMCallRecord | None = None) -> str:
        # DeepSeek 偶发返回缺 function 键的残缺 tool_call，回填错误让模型自行纠正
        function = call.get("function")
        if not isinstance(function, dict) or not function.get("name"):
            return json.dumps(
                ToolResult(
                    output=f"malformed tool call: {json.dumps(call, ensure_ascii=False)[:200]}",
                    is_error=True,
                ).__dict__,
                ensure_ascii=False,
            )
        name = function["name"]
        raw_args = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            if record is not None:
                record.tool_calls.append({"name": name, "arguments": arguments})
            output = self.tools.get(name).invoke(arguments)
            return json.dumps(
                {"output": output if isinstance(output, str) else output},
                ensure_ascii=False,
            )
        except Exception as exc:
            # 工具失败回填给模型自行纠正；两轮仍失败会在 max_turns 处崩溃
            return json.dumps(
                ToolResult(output=repr(exc), is_error=True).__dict__, ensure_ascii=False
            )
