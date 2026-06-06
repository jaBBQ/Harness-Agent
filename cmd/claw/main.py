import logging
import os

from internal.engine import new_agent_engine
from internal.provider import new_zhipu_openai_provider
from internal.tools import ReadFileTool, new_registry


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
    provider = new_zhipu_openai_provider("glm-4.5-air")

    # 初始化真实的 Tool Registry，并挂载 ReadFile 工具。
    registry = new_registry()
    registry.register(ReadFileTool(work_dir))
    enable_thinking = False

    # 实例化核心引擎。
    engine = new_agent_engine(provider, registry, work_dir, enable_thinking)

    # 发起任务指令。
    try:
        engine.run("请调用工具读取一下当前工作区目录下 hello.txt 文件的内容，并用一句话向我总结它说了什么。")
    except Exception as exc:
        logging.exception("引擎崩溃: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
