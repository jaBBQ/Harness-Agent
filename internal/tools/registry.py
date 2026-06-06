from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
from typing import Any

from internal.schema import ToolCall, ToolDefinition, ToolResult

ToolHandler = Callable[..., Any]


class BaseTool(ABC):
    """BaseTool 是所有具体工具必须实现的通用接口。"""

    @abstractmethod
    def name(self) -> str:
        """返回工具的全局唯一名称。"""
        raise NotImplementedError

    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回提交给大模型的工具元信息和参数 JSON Schema。"""
        raise NotImplementedError

    @abstractmethod
    def execute(self, arguments: Any) -> str:
        """接收大模型吐出的参数并执行具体业务逻辑。"""
        raise NotImplementedError


@dataclass(slots=True)
class FunctionTool(BaseTool):
    """将普通 Python 函数适配成 BaseTool。"""

    tool_name: str
    handler: ToolHandler
    tool_definition: ToolDefinition

    def name(self) -> str:
        return self.tool_name

    def definition(self) -> ToolDefinition:
        return self.tool_definition

    def execute(self, arguments: Any) -> str:
        output = self._execute_handler(arguments)
        return str(output)

    def _execute_handler(self, arguments: Any) -> Any:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass

        if arguments is None:
            return self.handler()
        if isinstance(arguments, dict):
            return self.handler(**arguments)
        if isinstance(arguments, list):
            return self.handler(*arguments)
        return self.handler(arguments)


class Registry(ABC):
    """Registry 定义了工具的注册与分发执行接口。"""

    @abstractmethod
    def register(self, tool: BaseTool) -> None:
        """挂载一个新的工具到系统中。"""
        raise NotImplementedError

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
        self._tools: dict[str, BaseTool] = {}

    def register(
        self,
        tool: BaseTool | str,
        handler: ToolHandler | None = None,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """注册 BaseTool，或兼容旧的函数式注册写法。"""
        if isinstance(tool, BaseTool):
            self._register_tool(tool)
            return

        if handler is None:
            raise ValueError("handler is required when registering a function tool")

        definition = ToolDefinition(
            name=tool,
            description=description,
            input_schema=input_schema or {"type": "object", "properties": {}},
        )
        self._register_tool(
            FunctionTool(
                tool_name=tool,
                handler=handler,
                tool_definition=definition,
            )
        )

    def register_tool(self, tool: BaseTool) -> None:
        """注册实现 BaseTool 接口的工具对象。"""
        self._register_tool(tool)

    def _register_tool(self, tool: BaseTool) -> None:
        name = tool.name()
        if name in self._tools:
            logging.warning("[Warning] 工具 '%s' 已经被注册，将被覆盖。", name)

        self._tools[name] = tool
        logging.info("[Registry] 成功挂载工具: %s", name)

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """直接按名称调用工具，供本地代码使用。"""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name].execute(kwargs or list(args) or None)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get_available_tools(self) -> list[ToolDefinition]:
        return [self._tools[name].definition() for name in self.names()]

    def execute(self, call: ToolCall) -> ToolResult:
        if call.name not in self._tools:
            return ToolResult(
                tool_call_id=call.id,
                output=f"Error: 系统中不存在名为 '{call.name}' 的工具。",
                is_error=True,
            )

        try:
            output = self._tools[call.name].execute(call.arguments)
            return ToolResult(
                tool_call_id=call.id,
                output=output,
                is_error=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_call_id=call.id,
                output=f"Error executing {call.name}: {exc}",
                is_error=True,
            )


def new_registry() -> Registry:
    return ToolRegistry()


NewRegistry = new_registry
