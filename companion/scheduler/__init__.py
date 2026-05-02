"""
Scheduler 模块 — 消息路由 + 主动循环 + Webhook 监听
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Optional

from companion.modules.registry import CompanionRegistry

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器 — 单 Agent + asyncio.Queue"""

    def __init__(self, max_size: int = 100):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._running = False

    async def enqueue(self, message: dict):
        """将消息加入队列"""
        try:
            await self.queue.put(message)
        except asyncio.QueueFull:
            logger.warning("Message queue full, dropping message")

    async def run(self, handler: Callable[[dict], None]):
        """运行消息循环"""
        self._running = True
        while self._running:
            try:
                message = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                handler(message)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue

    def stop(self):
        self._running = False


class ProactiveLoop:
    """主动触发循环 — 定时检查是否应该主动联系"""

    def __init__(
        self,
        registry: CompanionRegistry,
        on_trigger: Optional[Callable[[dict], None]] = None,
        check_interval: int = 300,  # 5 minutes
    ):
        self.registry = registry
        self.on_trigger = on_trigger
        self.check_interval = check_interval
        self._running = False

    async def run(self):
        """运行主动循环"""
        self._running = True
        while self._running:
            try:
                await self._check_trigger()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Proactive loop error: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_trigger(self):
        """检查是否应该触发主动联系"""
        decision = self.registry.trigger.compute()
        if decision.should_trigger and self.on_trigger:
            self.on_trigger({
                "type": "proactive_contact",
                "decision": {
                    "pull": decision.pull,
                    "nudge": decision.nudge,
                    "state": decision.state,
                },
                "timestamp": datetime.now().isoformat(),
            })

    def stop(self):
        self._running = False


class WebhookListener:
    """Webhook 监听 — 处理外部消息"""

    def __init__(self, registry: CompanionRegistry, router: MessageRouter):
        self.registry = registry
        self.router = router

    async def handle_message(self, message: dict):
        """处理外部传入的消息"""
        # Enrich with context
        message["received_at"] = datetime.now().isoformat()

        # Record interaction (new API)
        self.registry.memory.add_conversation(
            role="user",
            content=message.get("content", ""),
            timestamp=message["received_at"],
        )

        # Update HMM state
        self.registry.trigger.hmm.on_user_message()

        # Route to agent
        await self.router.enqueue(message)


class TrendingFetcher:
    """热搜预取器 — 定时抓取并缓存热点"""

    def __init__(
        self,
        registry: CompanionRegistry,
        fetch_interval: int = 14400,  # 4 hours
    ):
        self.registry = registry
        self.fetch_interval = fetch_interval
        self._running = False

    async def run(self):
        """运行定时预取"""
        self._running = True
        while self._running:
            try:
                await self._fetch()
                await asyncio.sleep(self.fetch_interval)
            except Exception as e:
                logger.error(f"Trending fetcher error: {e}")
                await asyncio.sleep(self.fetch_interval)

    async def _fetch(self):
        """执行预取（预留外部 API 接入点）"""
        # Placeholder: integrate with actual trending API
        # For now, just save some sample topics
        sample_topics = [
            {"title": "今日热点话题示例1"},
            {"title": "今日热点话题示例2"},
        ]
        self.registry.trending.save(sample_topics)

    def stop(self):
        self._running = False


async def start_companion(
    registry: CompanionRegistry,
    on_proactive_trigger: Optional[Callable[[dict], None]] = None,
) -> tuple[MessageRouter, ProactiveLoop, TrendingFetcher]:
    """启动 companion 系统"""
    router = MessageRouter()
    webhook = WebhookListener(registry, router)
    proactive = ProactiveLoop(registry, on_trigger=on_proactive_trigger)
    fetcher = TrendingFetcher(registry)

    # Expose webhook handler for external access
    router.webhook = webhook

    async def message_handler(msg: dict):
        logger.info(f"Processing message: {msg.get('content', '')[:50]}")
        # Agent processes the message (handled externally)

    # Start background tasks
    asyncio.create_task(router.run(message_handler))
    asyncio.create_task(proactive.run())
    asyncio.create_task(fetcher.run())

    logger.info("Companion system started")
    return router, proactive, fetcher
