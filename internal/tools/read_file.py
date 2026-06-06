import json
from pathlib import Path
from typing import Any

from internal.schema import ToolDefinition

from .registry import BaseTool


class ReadFileTool(BaseTool):
    """读取工作区内本地文件内容的工具。"""

    def __init__(self, work_dir: str, max_len: int = 8000) -> None:
        self.work_dir = Path(work_dir).resolve()
        self.max_len = max_len

    def name(self) -> str:
        return "read_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="读取指定路径的文件内容。请提供相对工作区的路径。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，如 cmd/claw/main.py",
                    },
                },
                "required": ["path"],
            },
        )

    def execute(self, arguments: Any) -> str:
        input_data = self._parse_arguments(arguments)
        relative_path = input_data.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("参数解析失败: path 必须是非空字符串")

        full_path = (self.work_dir / relative_path).resolve()
        self._ensure_inside_work_dir(full_path)

        try:
            content = full_path.read_bytes()
        except OSError as exc:
            raise OSError(f"打开或读取文件失败: {exc}") from exc

        if len(content) > self.max_len:
            prefix = content[: self.max_len].decode("utf-8", errors="replace")
            return f"{prefix}\n\n...[由于内容过长，已被系统截断至前 {self.max_len} 字节]..."

        return content.decode("utf-8", errors="replace")

    def _parse_arguments(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise ValueError(f"参数解析失败: {exc}") from exc
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("参数解析失败: 参数必须是 JSON object")

    def _ensure_inside_work_dir(self, path: Path) -> None:
        try:
            path.relative_to(self.work_dir)
        except ValueError as exc:
            raise PermissionError("拒绝读取工作区之外的文件") from exc


def new_read_file_tool(work_dir: str) -> ReadFileTool:
    return ReadFileTool(work_dir)


NewReadFileTool = new_read_file_tool
