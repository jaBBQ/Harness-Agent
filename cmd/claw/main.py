import json
import logging
import os

from internal.engine import new_agent_engine
from internal.provider import new_zhipu_claude_provider, new_zhipu_openai_provider
from internal.schema import ToolCall, ToolDefinition, ToolResult


# ==========================================
# 1. 伪造的 Tool Registry (用于测试 Provider 的工具提取能力)
# ==========================================
class MockRegistry:
    def get_available_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_weather",
                description="获取指定城市的当前天气情况。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                    },
                    "required": ["city"],
                },
            )
        ]

    def execute(self, call: ToolCall) -> ToolResult:
        city = ""
        arguments = call.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if isinstance(arguments, dict):
            city = str(arguments.get("city") or "")

        logging.info("  -> [Mock 工具执行] 获取 %s 的天气中...", city or call.name)
        return ToolResult(
            tool_call_id=call.id,
            output="API 返回：今天是晴天，气温 25 度。",
            is_error=False,
        )


# ==========================================
# 2. 组装运行
# ==========================================
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not os.getenv("ZHIPU_API_KEY"):
        logging.error("请先导出 ZHIPU_API_KEY 环境变量")
        return 1

    # 获取当前执行目录作为 WorkDir 物理边界。
    work_dir = os.getcwd()

    # 初始化真实的 Provider 大脑。
    # 这里可以切换为 new_zhipu_claude_provider("glm-4.5-air")。
    provider = new_zhipu_openai_provider("glm-4.5-air")
    registry = MockRegistry()
    enable_thinking = True

    # 实例化核心引擎。
    engine = new_agent_engine(provider, registry, work_dir, enable_thinking)

    # 发起任务指令。
    try:
        engine.run("我想去北京跑步，帮我查查天气适合吗？")
    except Exception as exc:
        logging.exception("引擎崩溃: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
