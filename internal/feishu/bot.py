from typing import Any


class FeishuBot:
    """Placeholder for Feishu bot callback handling."""

    def handle_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "payload": payload}
