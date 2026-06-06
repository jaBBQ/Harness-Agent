from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any

from internal.schema import ToolCall, ToolDefinition, ToolResult

ToolHandler = Callable[..., Any]


@dataclass(slots=True)
class RegisteredTool:
    """保存单个工具的执行函数与对外暴露的 Schema。"""

    handler: ToolHandler
    definition: ToolDefinition


class Registry(ABC):
    """Registry 定义了工具的注册与分发执行接口。"""

    @abstractmethod
    def get_available_tools(self) -> list[ToolDefinition]:
        """返回当前系统挂载的所有可用工具的 Schema。"""
        raise NotImplementedError

    @abstractmethod
    def execute(self, call: ToolCall) -> ToolResult:
        """实际执行模型请求的工具，并返回结果。"""
        raise NotImplementedError


class ToolRegistry(Registry):
    """工具注册表，负责保存工具定义并按 ToolCall 分发执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """注册工具执行函数及其 JSON Schema 描述。"""
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        definition = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object", "properties": {}},
        )
        self._tools[name] = RegisteredTool(handler=handler, definition=definition)

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """直接按名称调用工具，供本地代码使用。"""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name].handler(*args, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get_available_tools(self) -> list[ToolDefinition]:
        return [self._tools[name].definition for name in self.names()]

    def execute(self, call: ToolCall) -> ToolResult:
        if call.name not in self._tools:
            return ToolResult(
                tool_call_id=call.id,
                output=f"Tool not found: {call.name}",
                is_error=True,
            )

        try:
            output = self._execute_handler(self._tools[call.name].handler, call.arguments)
            return ToolResult(
                tool_call_id=call.id,
                output=str(output),
                is_error=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_call_id=call.id,
                output=str(exc),
                is_error=True,
            )

    def _execute_handler(self, handler: ToolHandler, arguments: Any) -> Any:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass

        if arguments is None:
            return handler()
        if isinstance(arguments, dict):
            return handler(**arguments)
        if isinstance(arguments, list):
            return handler(*arguments)
        return handler(arguments)
