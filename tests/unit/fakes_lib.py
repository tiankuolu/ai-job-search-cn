# 脚本化假模型实现：响应序列耗尽就地崩溃。

import json


def make_text_response(text: str, token_cost: int = 50) -> dict:
    """构造纯文本回复。"""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                    "tool_calls": None,
                }
            }
        ],
        "usage": {
            "prompt_tokens": token_cost,
            "completion_tokens": token_cost // 2 + 1,
        },
    }


def make_tool_call_response(
    call_id: str, name: str, arguments: dict
) -> dict:
    """构造一个工具调用回复。"""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 20},
    }


class ScriptedLLMClient:
    """按脚本顺序返回响应的假模型；脚本耗尽或断言失败立即抛错。"""

    def __init__(self, responses: list[dict], model: str = "scripted-fake") -> None:
        if not responses:
            raise ValueError("脚本化假模型至少需要一个响应")
        self.model = model
        self._responses = list(responses)
        self._index = 0
        self.calls: list[dict] = []

    def chat(self, messages: list, tools: list) -> dict:
        self.calls.append(
            {"messages": [dict(m) for m in messages], "tools": list(tools)}
        )
        if self._index >= len(self._responses):
            raise AssertionError(
                f"假模型脚本已耗尽（第 {self._index + 1} 次调用没有预设响应），"
                f"实际 agent 循环比预期多跑了 {self._index - len(self._responses) + 1} 轮"
            )
        response = self._responses[self._index]
        self._index += 1
        return response
