import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler
from typing import Any

import lark_oapi as lark
import lark_oapi.api.im.v1 as larkim

from internal.engine import AgentEngine, Reporter


class FeishuBot:
    """FeishuBot 封装飞书机器人配置与 Agent 业务流。"""

    def __init__(self, engine: AgentEngine) -> None:
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")
        if not app_id or not app_secret:
            raise RuntimeError("请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")

        self.client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        self.app_id = app_id
        self.app_secret = app_secret
        self.engine = engine

    def get_event_dispatcher(self) -> lark.EventDispatcherHandler:
        """构建飞书事件调度器，用于处理 /webhook/event POST 回调。"""
        encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")
        verify_token = os.getenv("FEISHU_VERIFY_TOKEN", "")

        return (
            lark.EventDispatcherHandler.builder(encrypt_key, verify_token)
            .register_p2_im_message_receive_v1(self._on_message_receive)
            .register_p2_im_message_message_read_v1(lambda _event: None)
            .build()
        )

    def handle_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        """兼容旧占位接口，便于本地直接喂入飞书事件 JSON 做 smoke test。"""
        dispatcher = self.get_event_dispatcher()
        response = dispatcher.do_without_validation(json.dumps(payload).encode("utf-8"))
        return {"ok": True, "response": response}

    def _on_message_receive(self, event: larkim.P2ImMessageReceiveV1) -> None:
        message = event.event.message
        chat_id = message.chat_id
        prompt = self._extract_text(message.content)

        logging.info("[Feishu] 收到会话 %s 消息: %s", chat_id, prompt)

        thread = threading.Thread(
            target=self.handle_agent_run,
            args=(chat_id, prompt),
            daemon=True,
        )
        thread.start()

    def handle_agent_run(self, chat_id: str, prompt: str) -> None:
        reporter = FeishuReporter(client=self.client, chat_id=chat_id)

        try:
            self.engine.run(prompt, reporter=reporter)
        except Exception as exc:
            logging.exception("[Feishu] Agent 运行崩溃")
            reporter.send_msg(f"Agent 运行崩溃: {exc}")

    def _extract_text(self, content: str | None) -> str:
        if not content:
            return ""

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return content.strip()

        text = data.get("text")
        if isinstance(text, str):
            return text.strip()
        return content.strip()


class FeishuReporter(Reporter):
    """将引擎事件格式化后发送到飞书会话。"""

    def __init__(self, client: lark.Client, chat_id: str) -> None:
        self.client = client
        self.chat_id = chat_id

    def send_msg(self, text: str) -> None:
        content = json.dumps({"text": text}, ensure_ascii=False)
        request = (
            larkim.CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                larkim.CreateMessageRequestBody.builder()
                .receive_id(self.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )

        response = self.client.im.v1.message.create(request)
        if not response.success():
            logging.warning(
                "[Feishu] 发送消息失败: code=%s msg=%s log_id=%s",
                response.code,
                response.msg,
                response.get_log_id(),
            )

    def OnThinking(self, ctx: object | None) -> None:  # noqa: N802
        self.send_msg("模型正在慢思考 (Thinking)...")

    def OnToolCall(self, ctx: object | None, tool_name: str, arguments: str) -> None:  # noqa: N802
        self.send_msg(f"正在执行工具: {tool_name}\n参数: {arguments}")

    def OnToolResult(
        self,
        ctx: object | None,
        tool_name: str,
        output: str,
        is_error: bool,
    ) -> None:  # noqa: N802
        if is_error:
            self.send_msg(f"执行报错 ({tool_name}):\n{output}")
        else:
            self.send_msg(f"执行成功 ({tool_name})")

    def OnMessage(self, ctx: object | None, message: str) -> None:  # noqa: N802
        self.send_msg(message)


def make_feishu_event_handler(bot: FeishuBot) -> type[BaseHTTPRequestHandler]:
    dispatcher = bot.get_event_dispatcher()

    class FeishuEventHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/webhook/event":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_request = lark.RawRequest()
            raw_request.uri = self.path
            raw_request.headers = {key: value for key, value in self.headers.items()}
            raw_request.body = self.rfile.read(content_length)

            raw_response = dispatcher.do(raw_request)
            self.send_response(raw_response.status_code or 200)
            for key, value in raw_response.headers.items():
                self.send_header(key, value)
            self.end_headers()
            if raw_response.content:
                self.wfile.write(raw_response.content)

        def log_message(self, format: str, *args: Any) -> None:
            logging.info("[FeishuHTTP] " + format, *args)

    return FeishuEventHandler
