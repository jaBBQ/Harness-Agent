import json
import os
import subprocess
from pathlib import Path
from typing import Any

from internal.schema import ToolDefinition

from .registry import BaseTool


class BashTool(BaseTool):
    """在工作区内执行 shell 命令的工具。"""

    def __init__(self, work_dir: str, timeout_seconds: int = 30, max_len: int = 8000) -> None:
        self.work_dir = Path(work_dir).resolve()
        self.timeout_seconds = timeout_seconds
        self.max_len = max_len

    def name(self) -> str:
        return "bash"

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name(),
            description=(
                "在当前工作区执行任意 shell 命令。支持链式命令、管道和重定向。"
                "返回标准输出(stdout)和标准错误(stderr)。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令，例如: ls -la 或 python -m compileall internal",
                    },
                },
                "required": ["command"],
            },
        )

    def execute(self, arguments: Any) -> str:
        input_data = self._parse_arguments(arguments)
        command = input_data.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("参数解析失败: command 必须是非空字符串")

        try:
            completed = subprocess.run(
                self._command_args(command),
                cwd=self.work_dir,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = self._combine_output(exc.stdout, exc.stderr)
            return (
                output
                + f"\n[警告: 命令执行超时({self.timeout_seconds}s)，已被系统强制终止。"
                "如果是启动常驻服务，请尝试将其转入后台。]"
            )

        output = self._combine_output(completed.stdout, completed.stderr)

        if completed.returncode != 0:
            return f"执行报错: exit status {completed.returncode}\n输出:\n{output}"

        if not output:
            return "命令执行成功，无终端输出。"

        return self._truncate(output)

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

    def _command_args(self, command: str) -> list[str]:
        if os.name == "nt":
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
        return ["bash", "-c", command]

    def _combine_output(self, stdout: str | bytes | None, stderr: str | bytes | None) -> str:
        parts = [self._to_text(stdout), self._to_text(stderr)]
        return "".join(part for part in parts if part)

    def _to_text(self, value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _truncate(self, output: str) -> str:
        output_bytes = output.encode("utf-8")
        if len(output_bytes) <= self.max_len:
            return output

        prefix = output_bytes[: self.max_len].decode("utf-8", errors="replace")
        return f"{prefix}\n\n...[终端输出过长，已截断至前 {self.max_len} 字节]..."


def new_bash_tool(work_dir: str) -> BashTool:
    return BashTool(work_dir)


NewBashTool = new_bash_tool
