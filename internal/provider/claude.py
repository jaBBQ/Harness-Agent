import json
import os
from typing import Any

from anthropic import Anthropic

from internal.schema import Message, Role, ToolCall, ToolDefinition

from .interface import LLMProvider


class ClaudeProvider(LLMProvider):
    """Anthropic Claude-compatible messages provider."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4/",
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self.max_tokens = max_tokens

    def generate(
        self,
        messages: list[Message],
        available_tools: list[ToolDefinition] | None,
    ) -> Message:
        anthropic_messages: list[dict[str, Any]] = []
        system_prompt = ""

        for message in messages:
            if message.role == Role.SYSTEM:
                system_prompt = message.content
                continue

            anthropic_message = self._message_to_anthropic(message)
            if anthropic_message is not None:
                anthropic_messages.append(anthropic_message)

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
        }
        if system_prompt:
            params["system"] = system_prompt

        # available_tools 为 None 时表示 Thinking 阶段，故意不挂载工具。
        # 空列表则表示 Action 阶段没有可用工具，两者请求形态相同但语义不同。
        tools = [self._tool_to_anthropic(tool) for tool in available_tools or []]
        if tools:
            params["tools"] = tools

        try:
            resp = self.client.messages.create(**params)
        except Exception as exc:
            raise RuntimeError(f"Claude/Zhipu API 请求失败: {exc}") from exc

        return self._message_from_anthropic(resp)

    def _message_to_anthropic(self, message: Message) -> dict[str, Any] | None:
        if message.role == Role.USER:
            if message.tool_call_id:
                return {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id,
                            "content": message.content,
                            "is_error": False,
                        }
                    ],
                }

            return {
                "role": "user",
                "content": [{"type": "text", "text": message.content}],
            }

        if message.role == Role.ASSISTANT:
            content: list[dict[str, Any]] = []
            if message.content:
                content.append({"type": "text", "text": message.content})

            for tool_call in message.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": self._arguments_to_input(tool_call.arguments),
                    }
                )

            if not content:
                return None

            return {"role": "assistant", "content": content}

        raise ValueError(f"Unsupported message role: {message.role}")

    def _tool_to_anthropic(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    def _message_from_anthropic(self, response: Any) -> Message:
        result = Message(role=Role.ASSISTANT, content="")

        for block in getattr(response, "content", None) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                result.content += getattr(block, "text", None) or ""
            elif block_type == "tool_use":
                result.tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=getattr(block, "name", ""),
                        arguments=getattr(block, "input", None) or {},
                    )
                )

        return result

    def _arguments_to_input(self, arguments: Any) -> dict[str, Any]:
        if arguments is None:
            return {}
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                return {"value": arguments}
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        return {"value": arguments}


def new_zhipu_claude_provider(model: str) -> ClaudeProvider:
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 ZHIPU_API_KEY 环境变量")

    return ClaudeProvider(
        model=model,
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )


NewZhipuClaudeProvider = new_zhipu_claude_provider
