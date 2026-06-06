from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    """Role 定义消息的角色，这是与大模型沟通的基石。"""

    # 系统提示词：确立 Agent 的性格与红线。
    SYSTEM = "system"

    # 用户输入 / 工具执行的返回结果 (Observation)。
    USER = "user"

    # 模型的输出：包含推理 (Reasoning) 或工具调用 (ToolCall)。
    ASSISTANT = "assistant"


@dataclass(slots=True)
class ToolCall:
    """ToolCall 代表模型请求调用某个具体的工具。"""

    # 工具调用的唯一 ID。
    id: str

    # 想要调用的工具名称，例如 "bash"。
    name: str

    # Arguments 存放 JSON 参数。
    # Python 中用原生 JSON 兼容类型承载，解析责任交给具体工具。
    arguments: dict[str, Any] | list[Any] | str | int | float | bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Message:
    """Message 代表上下文中传递的单条消息。"""

    role: Role

    # 存放纯文本内容。
    content: str

    # 如果模型决定调用工具，此字段将被填充，支持并行调用多个工具。
    tool_calls: list[ToolCall] = field(default_factory=list)

    # 如果这是对某个工具调用的响应，此字段必须填写，
    # 用于告知模型上下文的关联性。
    tool_call_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            data["tool_calls"] = [tool_call.to_dict() for tool_call in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


@dataclass(slots=True)
class ToolResult:
    """ToolResult 代表工具在本地执行完毕后返回的物理结果。"""

    tool_call_id: str

    # 工具执行的控制台输出或报错堆栈。
    output: str

    # 标记是否失败，供后续的驾驭工程进行错误自愈。
    is_error: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToolDefinition:
    """ToolDefinition 描述了一个大模型可以调用的工具元信息。"""

    name: str
    description: str

    # 对应 JSON Schema，供模型理解工具的输入结构。
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
