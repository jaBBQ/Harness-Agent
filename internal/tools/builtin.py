from pathlib import Path

from .bash import BashTool
from .read_file import ReadFileTool
from .registry import ToolRegistry
from .write_file import WriteFileTool


def edit(path: str, content: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def register_builtin_tools(registry: ToolRegistry, work_dir: str | None = None) -> None:
    if work_dir:
        registry.register(BashTool(work_dir))

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
