import logging
import os

from internal.engine import new_agent_engine
from internal.schema import Message, Role, ToolCall, ToolDefinition, ToolResult


# ==========================================
# 1. 伪造的大模型 Provider
# ==========================================
class MockProvider:
    def __init__(self) -> None:
        self.action_turn = 0

    # 模拟大模型的响应：第一轮请求执行 bash，第二轮输出最终结果。
    def generate(
        self,
        messages: list[Message],
        available_tools: list[ToolDefinition] | None,
    ) -> Message:
        if available_tools is None:
            return Message(
                role=Role.ASSISTANT,
                content="我会先检查当前目录文件，再根据观察结果给出结论。",
            )

        self.action_turn += 1
        if self.action_turn == 1:
            return Message(
                role=Role.ASSISTANT,
                content="让我来看看当前目录下有什么文件。",
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        name="bash",
                        arguments={"command": "ls -la"},
                    )
                ],
            )

        return Message(
            role=Role.ASSISTANT,
            content="我看到了文件列表，里面包含 main.go，任务完成！",
        )


# ==========================================
# 2. 伪造的 Tool Registry
# ==========================================
class MockRegistry:
    def get_available_tools(self) -> list[ToolDefinition]:
        return []

    def execute(self, call: ToolCall) -> ToolResult:
        # 直接返回一段伪造的终端输出。
        return ToolResult(
            tool_call_id=call.id,
            output="-rw-r--r--  1 user group  234 Oct 24 10:00 main.go\n",
            is_error=False,
        )


# ==========================================
# 3. 组装运行
# ==========================================
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 获取当前执行目录作为 WorkDir 物理边界。
    work_dir = os.getcwd()

    provider = MockProvider()
    registry = MockRegistry()
    enable_thinking = True

    # 实例化核心引擎。
    engine = new_agent_engine(provider, registry, work_dir, enable_thinking)

    # 发起任务指令。
    try:
        engine.run("帮我检查当前目录的文件")
    except Exception as exc:
        logging.exception("引擎崩溃: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
