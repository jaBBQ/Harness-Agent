from typing import Any

from .token_monitor import TokenMonitor


class PromptBuilder:
    """Builds prompts from user input and persisted memory."""

    def __init__(self, token_monitor: TokenMonitor) -> None:
        self.token_monitor = token_monitor

    def build(self, user_prompt: str, memory: dict[str, Any]) -> str:
        memory_text = "\n".join(f"{key}: {value}" for key, value in memory.items())
        sections = [
            "You are Harness Agent.",
            f"Memory:\n{memory_text or '(empty)'}",
            f"User:\n{user_prompt or '(empty prompt)'}",
        ]
        prompt = "\n\n".join(sections)
        self.token_monitor.observe(prompt)
        return prompt
