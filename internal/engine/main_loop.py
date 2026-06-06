from internal.context import PromptBuilder, TokenMonitor
from internal.memory import FileMemoryStore
from internal.provider import EchoProvider
from internal.tools import ToolRegistry, register_builtin_tools


class MainLoop:
    """Core orchestration loop for provider, context, memory, and tools."""

    def __init__(self) -> None:
        self.provider = EchoProvider()
        self.memory = FileMemoryStore()
        self.token_monitor = TokenMonitor()
        self.prompt_builder = PromptBuilder(self.token_monitor)
        self.tools = ToolRegistry()
        register_builtin_tools(self.tools)

    def run(self, user_prompt: str) -> str:
        prompt = self.prompt_builder.build(user_prompt, self.memory.load())
        response = self.provider.complete(prompt)
        self.memory.save({"last_prompt": user_prompt, "last_response": response})
        print(response)
        return response
