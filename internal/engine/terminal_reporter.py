class TerminalReporter:
    """Reporter 实现：在终端打印 Agent 状态。"""

    def OnThinking(self, ctx: object | None) -> None:  # noqa: N802
        print("\n[思考中] 模型正在推理...")

    def OnToolCall(self, ctx: object | None, tool_name: str, arguments: str) -> None:  # noqa: N802
        print(f"[调用工具] {tool_name}")
        display_args = arguments.replace("\n", "\\n").replace("\r", "\\r")
        if len(display_args) > 150:
            display_args = display_args[:150] + "... (已截断)"
        print(f"   参数: {display_args}")

    def OnToolResult(
        self,
        ctx: object | None,
        tool_name: str,
        output: str,
        is_error: bool,
    ) -> None:  # noqa: N802
        if is_error:
            print(f"[执行失败] {tool_name}")
            if output:
                print(f"   错误: {output}")
        else:
            print(f"[执行成功] {tool_name}")

    def OnMessage(self, ctx: object | None, message: str) -> None:  # noqa: N802
        if not message:
            return
        print(f"\nAgent 回复:\n{message}\n")


def new_terminal_reporter() -> TerminalReporter:
    return TerminalReporter()

