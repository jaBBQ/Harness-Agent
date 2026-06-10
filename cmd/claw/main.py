import argparse
import logging
import os
from http.server import ThreadingHTTPServer

from internal.engine import AgentEngine, new_agent_engine
from internal.feishu.bot import FeishuBot, make_feishu_event_handler
from internal.provider import new_zhipu_openai_provider
from internal.tools import BashTool, EditFileTool, ReadFileTool, WriteFileTool, new_registry


def build_engine() -> AgentEngine:
    if not os.getenv("ZHIPU_API_KEY"):
        raise RuntimeError("请先导出 ZHIPU_API_KEY 环境变量")

    # 获取当前执行目录作为 WorkDir 物理边界。
    work_dir = os.getcwd()

    # 初始化真实的 Provider 大脑。
    provider = new_zhipu_openai_provider("glm-4.5-air")

    # 初始化真实的 Tool Registry，并挂载极简工具集。
    registry = new_registry()
    registry.register(ReadFileTool(work_dir))
    registry.register(WriteFileTool(work_dir))
    registry.register(BashTool(work_dir))
    registry.register(EditFileTool(work_dir))
    enable_thinking = True

    # 实例化核心引擎。
    return new_agent_engine(provider, registry, work_dir, enable_thinking)


def serve_feishu(engine: AgentEngine, host: str, port: int) -> None:
    bot = FeishuBot(engine)
    handler = make_feishu_event_handler(bot)
    server = ThreadingHTTPServer((host, port), handler)
    logging.info("go-tiny-claw 飞书服务端已启动，正在监听 %s:%d", host, port)
    server.serve_forever()


# ==========================================
# 2. 组装运行
# ==========================================
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="claw")
    parser.add_argument("prompt", nargs="*", help="直接交给 Agent 执行的任务")
    parser.add_argument("--feishu", action="store_true", help="启动飞书事件回调 HTTP 服务")
    parser.add_argument("--host", default="0.0.0.0", help="飞书服务监听地址")
    parser.add_argument("--port", type=int, default=48080, help="飞书服务监听端口")
    args = parser.parse_args()

    try:
        engine = build_engine()
    except Exception as exc:
        logging.error("%s", exc)
        return 1

    if args.feishu:
        try:
            serve_feishu(engine, args.host, args.port)
        except KeyboardInterrupt:
            logging.info("收到退出信号，服务已停止")
            return 0
        except Exception as exc:
            logging.exception("服务器启动失败: %s", exc)
            return 1

    # 发起任务指令。
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = """
我当前目录下有 a.txt, b.txt, c.txt 三个文件。
为了节省时间，请你同时一次性读取这三个文件，并将它们的内容综合起来，告诉我它们分别记录了什么领域的信息。
"""

    try:
        engine.run(prompt)
    except Exception as exc:
        logging.exception("引擎崩溃: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
