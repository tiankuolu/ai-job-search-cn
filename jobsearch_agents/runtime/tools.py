# 工具协议包含名称、参数描述与可调用函数。

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """一个 agent 可调用的工具。parameters 是 JSON Schema 的参数定义。"""

    name: str
    description: str
    parameters: dict
    func: Callable[..., Any]

    def invoke(self, arguments: dict) -> Any:
        if not isinstance(arguments, dict):
            raise TypeError(f"工具 {self.name} 的参数必须是 JSON 对象，收到 {type(arguments)}")
        return self.func(**arguments)


@dataclass
class ToolResult:
    """工具执行结果。is_error 标记被模型看到，用于自行纠正参数。"""

    output: Any
    is_error: bool = False


class ToolRegistry:
    """一个 agent 持有的工具集合。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具名重复注册：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"未注册的工具：{name}")
        return self._tools[name]

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def names(self) -> list[str]:
        return list(self._tools)


def infer_schema(func: Callable, override: dict | None = None) -> dict:
    """从函数签名推导 JSON Schema 参数定义，override 补充签名表达不了的信息。

    类型映射：str -> string，int -> integer，float -> number，bool -> boolean，
    有默认值的参数不进 required。覆盖顺序：override 里同名的键最终生效。
    """
    type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        annotation = param.annotation
        json_type = type_map.get(annotation, "string")
        prop: dict[str, Any] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default
        properties[param_name] = prop
    if override:
        for key, value in override.items():
            if key == "required":
                required = value
            else:
                properties[key] = value
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
