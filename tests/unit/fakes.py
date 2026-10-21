"""脚本化假模型：按预设的响应序列回放，用于单元层控制流验证（GOAL.md §2.5）。

假模型满足 runtime.agent.LLMClient 协议：model 属性 + chat(messages, tools)。
每个响应是 OpenAI 兼容格式的字典；真实 LLM 的返回结构里 content 与
tool_calls 互斥，假模型不强制这一点，控制流按有无 tool_calls 分派。
"""

from .fakes_lib import ScriptedLLMClient, make_tool_call_response, make_text_response

__all__ = [
    "ScriptedLLMClient",
    "make_tool_call_response",
    "make_text_response",
]
