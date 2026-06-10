import logging
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Protocol

from internal.context import PromptComposer
from internal.provider import LLMProvider
from internal.schema import Message, Role, ToolCall
from internal.tools import Registry


class Reporter(Protocol):
    """Reporter 用于把引擎内部事件同步给外部 UI / 通知系统。"""

    def OnThinking(self, ctx: object | None) -> None:  # noqa: N802
        raise NotImplementedError

    def OnMessage(self, ctx: object | None, message: str) -> None:  # noqa: N802
        raise NotImplementedError

    def OnToolCall(self, ctx: object | None, tool_name: str, arguments: str) -> None:  # noqa: N802
        raise NotImplementedError

    def OnToolResult(
        self,
        ctx: object | None,
        tool_name: str,
        output: str,
        is_error: bool,
    ) -> None:  # noqa: N802
        raise NotImplementedError


@dataclass(slots=True)
class AgentEngine:
    """AgentEngine 是微型 OS 的核心驱动。"""

    provider: LLMProvider
    registry: Registry

    # WorkDir (工作区): 借鉴 OpenClaw 的理念，
    # Agent 必须有一个明确的物理边界。
    work_dir: str

    # EnableThinking (慢思考模式): 开启后引导模型进行更谨慎的推理与验证。
    enable_thinking: bool = False
    composer: PromptComposer | None = None

    def run(self, user_prompt: str, reporter: Reporter | None = None, ctx: object | None = None) -> None:
        """Run 启动 Agent 的生命周期。"""
        logging.info("[Engine] 引擎启动，锁定工作区: %s", self.work_dir)
        logging.info("[Engine] 慢思考模式 (Thinking Phase): %s", self.enable_thinking)

        composer = self.composer or PromptComposer(self.work_dir)

        # 1. 初始化会话的 Context (上下文内存)，动态注入 AGENTS.md 与 Skills。
        context_history = [
            composer.build(),
            Message(role=Role.USER, content=user_prompt),
        ]

        turn_count = 0

        # 2. The Main Loop: 心跳开始，标准的 ReAct 循环。
        while True:
            turn_count += 1
            logging.info("========== [Turn %d] 开始 ==========", turn_count)

            # 获取当前挂载的所有工具定义。
            available_tools = self.registry.get_available_tools()

            # Phase 1: 慢思考阶段 (Thinking) - 剥夺工具，强制规划。
            if self.enable_thinking:
                logging.info("[Engine][Phase 1] 剥夺工具访问权，强制进入慢思考与规划阶段...")
                if reporter is not None:
                    self._notify_reporter(lambda: reporter.OnThinking(ctx))
                try:
                    think_resp = self.provider.generate(context_history, None)
                except Exception as exc:
                    raise RuntimeError("Thinking 阶段生成失败") from exc

                if think_resp.content:
                    print(f" [内部思考 Trace]: {think_resp.content}")
                    context_history.append(think_resp)

            # Phase 2: 行动阶段 (Action) - 恢复工具，顺着规划执行。
            logging.info("[Engine][Phase 2] 恢复工具挂载，等待模型采取行动...")
            try:
                action_resp = self.provider.generate(context_history, available_tools)
            except Exception as exc:
                raise RuntimeError("Action 阶段生成失败") from exc

            # 将模型的响应完整追加到上下文历史中。
            context_history.append(action_resp)

            # 如果模型回复了纯文本，打印出来。
            if action_resp.content:
                print(f" [对外回复]: {action_resp.content}")
                if reporter is not None:
                    self._notify_reporter(lambda: reporter.OnMessage(ctx, action_resp.content))

            # 3. 退出条件判断。
            # 如果模型没有请求任何工具调用，说明它认为任务已经完成，跳出循环。
            if not action_resp.tool_calls:
                logging.info("[Engine] 模型未请求调用工具，任务宣告完成。")
                break

            # 4. 并发执行行动 (Action) 与获取观察结果 (Observation)。
            logging.info("[Engine] 模型请求并发调用 %d 个工具...", len(action_resp.tool_calls))

            observation_msgs = self._execute_tool_calls_parallel(ctx, reporter, action_resp.tool_calls)
            logging.info("[Engine] 所有并发工具执行完毕，开始聚合观察结果 (Observation)...")
            context_history.extend(observation_msgs)

            # 循环回到开头，模型将带着新加入的 Observation
            # 继续它的下一轮思考。

    def _execute_tool_calls_parallel(
        self,
        ctx: object | None,
        reporter: Reporter | None,
        tool_calls: list[ToolCall],
    ) -> list[Message]:
        observation_msgs: list[Message | None] = [None] * len(tool_calls)

        with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
            futures = [
                executor.submit(
                    self._execute_one_tool_call,
                    ctx,
                    reporter,
                    index,
                    tool_call,
                    observation_msgs,
                )
                for index, tool_call in enumerate(tool_calls)
            ]
            wait(futures)
            for future in futures:
                future.result()

        return [msg for msg in observation_msgs if msg is not None]

    def _execute_one_tool_call(
        self,
        ctx: object | None,
        reporter: Reporter | None,
        index: int,
        tool_call: ToolCall,
        observation_msgs: list[Message | None],
    ) -> None:
        logging.info("  -> [Go-%d] 触发并行执行: %s", index, tool_call.name)
        if reporter is not None:
            self._notify_reporter(
                lambda: reporter.OnToolCall(ctx, tool_call.name, self._stringify_arguments(tool_call.arguments))
            )

        result = self.registry.execute(tool_call)

        if result.is_error:
            logging.info("  -> [Go-%d] 工具执行报错: %s", index, result.output)
        else:
            logging.info("  -> [Go-%d] 工具执行成功 (返回 %d 字节)", index, len(result.output))

        if reporter is not None:
            display_output = result.output
            if len(display_output) > 200:
                display_output = display_output[:200] + "... (已截断)"
            self._notify_reporter(
                lambda: reporter.OnToolResult(ctx, tool_call.name, display_output, result.is_error)
            )

        observation_msgs[index] = Message(
            role=Role.USER,
            content=result.output,
            tool_call_id=tool_call.id,
        )

    def _notify_reporter(self, callback) -> None:
        try:
            callback()
        except Exception as exc:
            logging.warning("[Engine] Reporter 回调失败: %s", exc)

    def _stringify_arguments(self, arguments) -> str:
        if isinstance(arguments, str):
            return arguments
        return str(arguments)


def new_agent_engine(
    provider: LLMProvider,
    registry: Registry,
    work_dir: str,
    enable_thinking: bool = False,
) -> AgentEngine:
    return AgentEngine(
        provider=provider,
        registry=registry,
        work_dir=work_dir,
        enable_thinking=enable_thinking,
        composer=PromptComposer(work_dir),
    )
