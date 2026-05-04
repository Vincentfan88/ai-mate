"""
Scheduler 模块 — 消息路由 + 主动循环 + Webhook 监听
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Callable, Dict, Optional

import httpx

from companion.modules.registry import CompanionRegistry

logger = logging.getLogger(__name__)


def _now_bj() -> datetime:
    """获取北京时间 (UTC+8) 的 naive datetime，用于本地时间比较。"""
    from datetime import timezone
    utc_now = datetime.now(timezone.utc)
    # UTC+8
    return (utc_now.replace(tzinfo=None) + __import__('datetime').timedelta(hours=8))


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
            except Exception as e:
                logger.error(f"MessageRouter error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

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
        now = _now_bj()

        # ── 预检查：最近 30 分钟内有用户对话则不主动联系 ──
        try:
            recent = self.registry.memory.get_recent_interactions(limit=10)
            for ix in recent:
                ts = ix.get("timestamp", "")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        if (now - dt).total_seconds() < 1800:
                            logger.debug(f"Proactive: skipped — user interacted {int((now-dt).total_seconds()/60)}min ago")
                            return
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            logger.debug(f"Proactive pre-check skipped: {e}")

        # 检查到期时间事件（高优先级）
        try:
            due_events = self.registry.time_awareness.check_pending(now=now)
            if due_events:
                event_descs = [f"{ev.original_text}: {ev.content}" for ev in due_events]
                event = {
                    "type": "time_event_trigger",
                    "events": event_descs,
                    "timestamp": now.isoformat(),
                }
                if self.on_trigger and asyncio.iscoroutinefunction(self.on_trigger):
                    await self.on_trigger(event)
                elif self.on_trigger:
                    self.on_trigger(event)
                return
        except Exception as e:
            logger.debug(f"Time event check skipped: {e}")

        # 检查纪念日（高优先级）— 使用统一 time_awareness
        anniversary_hits = []
        try:
            anniversary_hits = self.registry.time_awareness.check_anniversaries_today(now=now)
        except Exception as e:
            logger.debug(f"Anniversary check skipped: {e}")

        if anniversary_hits:
            event = {
                "type": "anniversary_trigger",
                "anniversaries": anniversary_hits,
                "timestamp": _now_bj().isoformat(),
            }
            if self.on_trigger and asyncio.iscoroutinefunction(self.on_trigger):
                await self.on_trigger(event)
            elif self.on_trigger:
                self.on_trigger(event)
            return

        # 检查习惯（今日 emoji/口头禅）
        catchphrase = None
        try:
            daily_emoji = self.registry.habits.get_daily_emoji()
            catchphrase = self.registry.habits.get_catchphrase()
        except Exception as e:
            logger.debug(f"Habit check skipped: {e}")

        decision = self.registry.trigger.compute()
        if decision.should_trigger and self.on_trigger:
            event = {
                "type": "proactive_contact",
                "decision": {
                    "pull": decision.pull,
                    "hold_back": decision.hold_back,
                    "nudge": decision.nudge,
                    "state": decision.state,
                    "daily_emoji": daily_emoji,
                    "catchphrase": catchphrase,
                },
                "timestamp": _now_bj().isoformat(),
            }
            # 支持同步和异步回调
            if asyncio.iscoroutinefunction(self.on_trigger):
                await self.on_trigger(event)
            else:
                self.on_trigger(event)

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
        message["received_at"] = _now_bj()

        # Record interaction (new API)
        self.registry.memory.add_conversation(
            role="user",
            content=message.get("content", ""),
            timestamp=message["received_at"].isoformat(),
        )

        # Extract time events from user message
        try:
            self.registry.time_awareness.extract_from_message(
                message.get("content", ""),
                now=message["received_at"],
            )
        except Exception:
            pass  # Time extraction is optional

        # Update HMM state
        self.registry.trigger.hmm.on_user_message()

        # Route to agent
        await self.router.enqueue(message)


class TrendingFetcher:
    """热搜预取器 — 定时用 LLM 生成热点话题"""

    def __init__(
        self,
        registry: CompanionRegistry,
        fetch_interval: int = 14400,  # 4 hours
        api_key: str = "",
        api_base: str = "",
        model: str = "",
    ):
        self.registry = registry
        self.fetch_interval = fetch_interval
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
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
        """执行预取 — 百度热搜优先，LLM 兜底"""
        # ── Path 1: 百度热搜（真实热点） ──
        result = await self._fetch_baidu()
        if result:
            return

        # ── Path 2: LLM API 兜底生成 ──
        if self.api_key and self.api_base:
            result = await self._fetch_llm()
            if result:
                return

        logger.warning("Trending: all fetch paths failed")

    async def _fetch_llm(self) -> bool:
        """通过 LLM API生成热点话题"""
        today = _now_bj().strftime("%Y年%m月%d日")
        system_prompt = (
            "你是一个了解中国时事的助手。请根据当前日期，生成20个当天可能热门的"
            "社会话题标题（如新闻事件、节日、体育、娱乐等）。"
            "每行一个话题，不要编号，不要解释。"
            f"当前日期：{today}"
        )
        try:
            api_url = f"{self.api_base.rstrip('/')}/chat/completions"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "system", "content": system_prompt}],
                        "max_tokens": 1000,
                        "temperature": 0.8,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            topics = [line.strip() for line in content.strip().split("\n") if line.strip()]
            if topics:
                result = [{"title": t} for t in topics[:20]]
                self.registry.trending.save(result)
                logger.info(f"Trending: fetched {len(result)} topics via LLM")
                return True
        except Exception as e:
            logger.warning(f"Trending: LLM fetch failed: {e}")
        return False

    async def _fetch_baidu(self) -> bool:
        """通过百度热搜 fallback"""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                r = await client.get(
                    "https://top.baidu.com/board?tab=realtime",
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                )
            html = r.text
            topics = re.findall(r'"word":"([^"]+)"', html)
            if topics:
                result = [{"title": t} for t in topics[:20]]
                self.registry.trending.save(result)
                logger.info(f"Trending: fetched {len(result)} topics from Baidu")
                return True
        except Exception as e:
            logger.error(f"Trending: Baidu fetch failed: {e}")
        return False

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
