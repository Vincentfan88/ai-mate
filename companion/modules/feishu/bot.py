"""飞书 Bot — 长连接（WebSocket）集成。

使用 lark-oapi SDK 实现飞书长连接 Bot：
- daemon thread 运行 lark.ws.Client 接收事件
- asyncio.run_coroutine_threadsafe 调度到主事件循环
- API client 回复消息

使用方式:
    bot = FeishuBot("app_id", "app_secret", asyncio.get_event_loop())
    bot.set_agent_getter(lambda: my_agent)
    bot.start()
    ...
    bot.stop()
"""

import asyncio
import json
import logging
import re
import threading
from typing import Callable, Optional

import lark_oapi as lark

logger = logging.getLogger(__name__)

# ── 公共常量 ──────────────────────────────────────────────────

MESSAGE_TYPE_TEXT = "text"
MAX_REPLY_LENGTH = 2000  # 飞书单条消息长度限制

# ── FeishuBot ─────────────────────────────────────────────────


class FeishuBot:
    """飞书长连接 Bot。

    在 daemon thread 中运行 ``lark.ws.Client`` 接收事件。
    消息处理通过 ``asyncio.run_coroutine_threadsafe`` 调度到主事件循环，
    保证 agent（共享 CompanionRegistry）的线程安全访问。

    属性:
        is_running: Bot 是否正在运行
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        loop: asyncio.AbstractEventLoop,
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._loop = loop

        # API client（sync）— 用于回复消息
        self._api_client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

        # Agent 获取函数 — 由外部注入，懒加载
        self._agent_getter: Optional[Callable[[], object]] = None

        # 线程 / WS 客户端
        self._thread: Optional[threading.Thread] = None
        self._ws_client: Optional[lark.ws.Client] = None
        self._running = False
        self._ready = threading.Event()

    # ── 属性 ──────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        """WS 连接状态（线程安全）。"""
        return self._ready.is_set()

    # ── 生命周期 ──────────────────────────────────────────

    def set_agent_getter(self, getter: Callable[[], object]) -> None:
        """设置 agent 获取函数。

        getter 在首次收到消息时被调用（在主事件循环上），
        实现 agent 的懒加载。
        """
        self._agent_getter = getter

    def start(self) -> None:
        """启动 Bot（daemon thread）。"""
        if self._running:
            logger.warning("FeishuBot 已在运行")
            return

        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_ws,
            name="feishu-bot",
            daemon=True,
        )
        self._thread.start()
        logger.info("FeishuBot 启动中...")

    def stop(self) -> None:
        """停止 Bot。"""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception:
                pass
            self._ws_client = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._ready.clear()
        logger.info("FeishuBot 已停止")

    # ── WS 线程 ───────────────────────────────────────────

    def _run_ws(self) -> None:
        """在 daemon thread 中运行 ``lark.ws.Client``。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            handler = lark.ws.EventHandler()
            handler.register("im.message.receive_v1", self._on_ws_event)

            self._ws_client = lark.ws.Client.builder() \
                .app_id(self._app_id) \
                .app_secret(self._app_secret) \
                .event_handler(handler) \
                .build()

            self._ready.set()

            # start() 是阻塞的，SDK 内部维护 WS 连接
            self._ws_client.start()

        except Exception as e:
            logger.error("FeishuBot WS 异常退出: %s", e)
            self._ready.clear()
        finally:
            loop.close()

    # ── 事件处理 ──────────────────────────────────────────

    def _on_ws_event(self, event) -> None:
        """WS 事件回调 — 在 daemon thread 中执行。

        立即返回（ack），将实际处理调度到主事件循环。
        """
        if not self._running:
            return

        try:
            message = event.event.message
            if message.message_type != MESSAGE_TYPE_TEXT:
                return

            content = json.loads(message.content)
            text = self._clean_text(content.get("text", ""))
            if not text:
                return

            chat_id = message.chat_id
            if not chat_id:
                return

            # 调度到主事件循环
            asyncio.run_coroutine_threadsafe(
                self._handle_message(chat_id, text),
                self._loop,
            )

        except Exception as e:
            logger.warning("FeishuBot 事件处理异常: %s", e)

    @staticmethod
    def _clean_text(raw: str) -> str:
        """清理消息文本：去除 @ 提及和前后空白。"""
        # 去除飞书 @ 提及格式：@_user_xxx 或 @username
        text = re.sub(r"@_user_\S+", "", raw)
        text = re.sub(r"@\S+", "", text)
        return text.strip()

    async def _handle_message(self, chat_id: str, text: str) -> None:
        """处理消息并回复 — 在主事件循环中执行。"""
        if not self._agent_getter:
            logger.warning("FeishuBot 未设置 agent_getter")
            return

        agent = self._agent_getter()
        if not agent:
            return

        try:
            response = await agent.run(text)
            if not response:
                response = "嗯~ 我在听呢，你想说什么呀？"
            if response.startswith("LLM call failed"):
                response = "抱歉，我刚刚走神了… 能再说一遍吗？"
        except Exception as e:
            logger.error("FeishuBot agent.run 异常: %s", e, exc_info=True)
            response = "抱歉，我出了点问题… 请稍后再试。"

        await self._send_reply(chat_id, response)

    async def _send_reply(self, chat_id: str, text: str) -> None:
        """通过飞书 API 发送回复消息。"""
        if len(text) > MAX_REPLY_LENGTH:
            text = text[: MAX_REPLY_LENGTH - 3] + "..."

        content = json.dumps({"text": text})
        request = lark.im.v1.CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                lark.im.v1.CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type(MESSAGE_TYPE_TEXT)
                    .content(content)
                    .build()
            ).build()

        # lark.Client 是同步的，用 run_in_executor 避免阻塞主循环
        try:
            await self._loop.run_in_executor(
                None,
                self._api_client.im.v1.message.create,
                request,
            )
        except Exception as e:
            logger.warning("FeishuBot 发送消息失败: %s", e)
