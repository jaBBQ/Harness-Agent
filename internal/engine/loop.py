import logging
from dataclasses import dataclass

from internal.provider import LLMProvider
from internal.schema import Message, Role
from internal.tools import Registry


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

    def run(self, user_prompt: str) -> None:
        """Run 启动 Agent 的生命周期。"""
        logging.info("[Engine] 引擎启动，锁定工作区: %s", self.work_dir)
        logging.info("[Engine] 慢思考模式 (Thinking Phase): %s", self.enable_thinking)

        # 1. 初始化会话的 Context (上下文内存)。
        # 在真实的场景中，这里会由动态 Prompt 组装器加载 AGENTS.md。
        # 目前先硬编码。
        context_history = [
            Message(
                role=Role.SYSTEM,
                content=(
                    "You are go-tiny-claw, an expert coding assistant. "
                    "You have full access to tools in the workspace."
                ),
            ),
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

            # 3. 退出条件判断。
            # 如果模型没有请求任何工具调用，说明它认为任务已经完成，跳出循环。
            if not action_resp.tool_calls:
                logging.info("[Engine] 模型未请求调用工具，任务宣告完成。")
                break

            # 4. 执行行动 (Action) 与获取观察结果 (Observation)。
            logging.info("[Engine] 模型请求调用 %d 个工具...", len(action_resp.tool_calls))

            for tool_call in action_resp.tool_calls:
                logging.info(
                    "  -> 执行工具: %s, 参数: %s",
                    tool_call.name,
                    tool_call.arguments,
                )

                # 通过 Registry 路由并执行底层工具。
                result = self.registry.execute(tool_call)

                if result.is_error:
                    logging.info("  -> 工具执行报错: %s", result.output)
                else:
                    logging.info("  -> 工具执行成功 (返回 %d 字节)", len(result.output))

                # 将工具执行的观察结果 (Observation) 封装为 User Message
                # 追加到上下文中。
                # 注意：tool_call_id 必须携带，这是维系大模型推理链条的关键。
                observation_msg = Message(
                    role=Role.USER,
                    content=result.output,
                    tool_call_id=tool_call.id,
                )
                context_history.append(observation_msg)

            # 循环回到开头，模型将带着新加入的 Observation
            # 继续它的下一轮思考。


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
    )
