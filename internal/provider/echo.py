from internal.schema import Message, Role, ToolDefinition

from .interface import LLMProvider


class EchoProvider(LLMProvider):
    """Development provider that echoes the assembled prompt."""

    def generate(
        self,
        messages: list[Message],
        available_tools: list[ToolDefinition] | None,
    ) -> Message:
        content = "\n".join(message.content for message in messages)
        tool_names = ", ".join(tool.name for tool in available_tools or [])
        if tool_names:
            content = f"{content}\n\nAvailable tools: {tool_names}"
        return Message(role=Role.ASSISTANT, content=f"EchoProvider response:\n{content}")

    def complete(self, prompt: str) -> str:
        return f"EchoProvider response:\n{prompt}"
