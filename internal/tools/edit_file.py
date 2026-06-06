import json
from pathlib import Path
from typing import Any

from internal.schema import ToolDefinition

from .registry import BaseTool


class EditFileTool(BaseTool):
    """对工作区内现有文件进行局部字符串替换的工具。"""

    def __init__(self, work_dir: str) -> None:
        self.work_dir = Path(work_dir).resolve()

    def name(self) -> str:
        return "edit_file"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description=(
                "对现有文件进行局部的字符串替换。这比重写整个文件更安全、更快速。"
                "请提供足够的 old_text 上下文以确保匹配的唯一性。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径",
                    },
                    "old_text": {
                        "type": "string",
                        "description": (
                            "文件中原有的文本。必须包含足够的上下文（建议上下各多包含几行），"
                            "以确保在文件中的唯一性。"
                        ),
                    },
                    "new_text": {
                        "type": "string",
                        "description": "要替换成的新文本",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        )

    def execute(self, arguments: Any) -> str:
        input_data = self._parse_arguments(arguments)
        relative_path = input_data.get("path")
        old_text = input_data.get("old_text")
        new_text = input_data.get("new_text")

        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("参数解析失败: path 必须是非空字符串")
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("参数解析失败: old_text 必须是非空字符串")
        if not isinstance(new_text, str):
            raise ValueError("参数解析失败: new_text 必须是字符串")

        full_path = (self.work_dir / relative_path).resolve()
        self._ensure_inside_work_dir(full_path)

        try:
            content = full_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OSError(f"读取文件失败: {exc}") from exc

        match_count = content.count(old_text)
        if match_count == 0:
            raise ValueError("未找到 old_text，请提供文件中实际存在的原文片段")
        if match_count > 1:
            raise ValueError(f"old_text 匹配到 {match_count} 处，请提供更长上下文以确保唯一性")

        updated = content.replace(old_text, new_text, 1)
        try:
            full_path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            raise OSError(f"写入文件失败: {exc}") from exc

        return f"成功修改文件: {relative_path}"

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
            raise PermissionError("拒绝修改工作区之外的文件") from exc


def new_edit_file_tool(work_dir: str) -> EditFileTool:
    return EditFileTool(work_dir)


NewEditFileTool = new_edit_file_tool
