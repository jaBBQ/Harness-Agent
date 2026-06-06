import json
from pathlib import Path
from typing import Any

from internal.schema import ToolDefinition

from .registry import BaseTool


class WriteFileTool(BaseTool):
    """创建或覆盖写入工作区内文件的工具。"""

    def __init__(self, work_dir: str) -> None:
        self.work_dir = Path(work_dir).resolve()

    def name(self) -> str:
        return "write_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description="创建或覆盖写入一个文件。如果目录不存在会自动创建。请提供相对于工作区的相对路径。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径，如 src/main.py",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的完整文件内容",
                    },
                },
                "required": ["path", "content"],
            },
        )

    def execute(self, arguments: Any) -> str:
        input_data = self._parse_arguments(arguments)
        relative_path = input_data.get("path")
        content = input_data.get("content")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("参数解析失败: path 必须是非空字符串")
        if not isinstance(content, str):
            raise ValueError("参数解析失败: content 必须是字符串")

        full_path = (self.work_dir / relative_path).resolve()
        self._ensure_inside_work_dir(full_path)

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise OSError(f"写入文件失败: {exc}") from exc

        return f"成功将内容写入到文件: {relative_path}"

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
            raise PermissionError("拒绝写入工作区之外的文件") from exc


def new_write_file_tool(work_dir: str) -> WriteFileTool:
    return WriteFileTool(work_dir)


NewWriteFileTool = new_write_file_tool
