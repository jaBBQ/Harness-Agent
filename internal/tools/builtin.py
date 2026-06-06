import subprocess
from pathlib import Path

from .read_file import ReadFileTool
from .registry import ToolRegistry
from .write_file import WriteFileTool


def bash(command: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else result.stderr


def edit(path: str, content: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def register_builtin_tools(registry: ToolRegistry, work_dir: str | None = None) -> None:
    registry.register(
        "bash",
        bash,
        description="Execute a shell command and return stdout or stderr.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run."},
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory.",
                },
            },
            "required": ["command"],
        },
    )
    registry.register(
        "edit",
        edit,
        description="Write text content to a file path.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
    )
    if work_dir:
        registry.register(ReadFileTool(work_dir))
        registry.register(WriteFileTool(work_dir))
