import json
import os
from typing import Any

from openai import OpenAI

from internal.schema import Message, Role, ToolCall, ToolDefinition

from .interface import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible chat completions provider."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4/",
    ) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(
        self,
        messages: list[Message],
        available_tools: list[ToolDefinition] | None,
    ) -> Message:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": [self._message_to_openai(message) for message in messages],
        }

        tools = [self._tool_to_openai(tool) for tool in available_tools or []]
        if tools:
            params["tools"] = tools

        try:
            resp = self.client.chat.completions.create(**params)
        except Exception as exc:
            raise RuntimeError(f"OpenAI/Zhipu API 请求失败: {exc}") from exc

        choices = resp.choices or []
        if not choices:
            raise RuntimeError("API 返回了空的 choices")

        return self._message_from_openai(choices[0].message)

    def _message_to_openai(self, message: Message) -> dict[str, Any]:
        if message.role == Role.SYSTEM:
            return {"role": "system", "content": message.content}

        if message.role == Role.USER:
            if message.tool_call_id:
                return {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content,
                }
            return {"role": "user", "content": message.content}

        if message.role == Role.ASSISTANT:
            data: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or None,
            }
            if message.tool_calls:
                data["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": self._arguments_to_json(tool_call.arguments),
                        },
                    }
                    for tool_call in message.tool_calls
                ]
            return data

        raise ValueError(f"Unsupported message role: {message.role}")

    def _tool_to_openai(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }

    def _message_from_openai(self, message: Any) -> Message:
        result = Message(
            role=Role.ASSISTANT,
            content=getattr(message, "content", None) or "",
        )

        for tool_call in getattr(message, "tool_calls", None) or []:
            if getattr(tool_call, "type", None) != "function":
                continue

            result.tool_calls.append(
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=tool_call.function.arguments,
                )
            )

        return result

    def _arguments_to_json(self, arguments: Any) -> str:
        if isinstance(arguments, str):
            return arguments
        return json.dumps(arguments, ensure_ascii=False)


def new_zhipu_openai_provider(model: str) -> OpenAIProvider:
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 ZHIPU_API_KEY 环境变量")

    return OpenAIProvider(
        model=model,
        api_key=api_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )


NewZhipuOpenAIProvider = new_zhipu_openai_provider
