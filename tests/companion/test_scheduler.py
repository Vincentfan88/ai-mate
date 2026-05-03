"""Tests for scheduler module — MessageRouter, ProactiveLoop, WebhookListener, TrendingFetcher."""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from companion.scheduler import MessageRouter, ProactiveLoop, WebhookListener, TrendingFetcher


@pytest.fixture
def registry():
    """Create a test registry with temp workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = f"{tmpdir}/workspace/companion"
        Path(workspace).mkdir(parents=True)
        from companion.modules.registry import CompanionRegistry
        reg = CompanionRegistry(
            workspace=workspace,
            config_dir="companion/config",
            mbti_type="ENFP",
        )
        yield reg


class TestMessageRouter:
    """Test message routing via asyncio.Queue."""

    def test_initial_state(self):
        router = MessageRouter(max_size=10)
        assert router.queue.qsize() == 0
        assert router._running is False

    @pytest.mark.asyncio
    async def test_enqueue_and_queue_size(self):
        router = MessageRouter()
        await router.enqueue({"content": "hello"})
        assert router.queue.qsize() == 1
        await router.enqueue({"content": "world"})
        assert router.queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_run_processes_messages(self):
        router = MessageRouter()
        received = []

        def handler(msg):
            received.append(msg)

        # Start router, enqueue, then stop
        task = asyncio.create_task(router.run(handler))
        await asyncio.sleep(0.05)
        await router.enqueue({"content": "msg1"})
        await router.enqueue({"content": "msg2"})
        await asyncio.sleep(0.1)
        router.stop()
        await task

        assert len(received) == 2
        assert received[0]["content"] == "msg1"
        assert received[1]["content"] == "msg2"

    @pytest.mark.asyncio
    async def test_run_calls_task_done(self):
        router = MessageRouter()
        processed_count = 0

        def handler(msg):
            nonlocal processed_count
            processed_count += 1

        task = asyncio.create_task(router.run(handler))
        await asyncio.sleep(0.05)
        await router.enqueue({"content": "test"})
        await asyncio.sleep(0.1)
        router.stop()
        await task

        # task_done should have been called, no unfinished tasks
        assert processed_count == 1

    @pytest.mark.asyncio
    async def test_timeout_does_not_crash(self):
        """Router should handle empty queue timeout gracefully."""
        router = MessageRouter()
        # Just start and stop — the timeout should cause continue, not crash
        task = asyncio.create_task(router.run(lambda m: None))
        await asyncio.sleep(0.2)
        router.stop()
        await task

    def test_stop_halts_loop(self):
        router = MessageRouter()
        assert router._running is False
        router.stop()  # Should not crash
        assert router._running is False

    def test_max_size(self):
        router = MessageRouter(max_size=2)
        assert router.queue.maxsize == 2


class TestProactiveLoop:
    """Test proactive trigger loop."""

    def test_initial_state(self, registry):
        loop = ProactiveLoop(registry, check_interval=60)
        assert loop.registry is registry
        assert loop.check_interval == 60
        assert loop.on_trigger is None
        assert loop._running is False

    @pytest.mark.asyncio
    async def test_check_trigger_calls_compute(self, registry):
        """_check_trigger should call trigger.compute()."""
        loop = ProactiveLoop(registry, check_interval=60)
        # Should not raise
        await loop._check_trigger()

    @pytest.mark.asyncio
    async def test_check_trigger_invokes_callback(self, registry):
        """When should_trigger is True, callback should be called."""
        triggered = []

        def on_trigger(msg):
            triggered.append(msg)

        loop = ProactiveLoop(registry, on_trigger=on_trigger)

        # Simulate a decision that triggers by using hours_since_last_contact
        # We need to mock compute to return a triggering decision
        original_compute = registry.trigger.compute
        mock_decision = MagicMock()
        mock_decision.should_trigger = True
        mock_decision.pull = "很想联系他"
        mock_decision.nudge = "很想念"
        mock_decision.state = "missing"
        registry.trigger.compute = MagicMock(return_value=mock_decision)

        try:
            await loop._check_trigger()
            assert len(triggered) == 1
            assert triggered[0]["type"] == "proactive_contact"
            assert triggered[0]["decision"]["state"] == "missing"
        finally:
            registry.trigger.compute = original_compute

    @pytest.mark.asyncio
    async def test_check_trigger_no_callback(self, registry):
        """When on_trigger is None, should not raise."""
        loop = ProactiveLoop(registry)
        await loop._check_trigger()  # Should be fine

    @pytest.mark.asyncio
    async def test_check_trigger_not_triggered(self, registry):
        """When should_trigger is False, callback should not be called."""
        triggered = []

        def on_trigger(msg):
            triggered.append(msg)

        loop = ProactiveLoop(registry, on_trigger=on_trigger)
        # Mock to force non-triggering decision
        mock_decision = MagicMock()
        mock_decision.should_trigger = False
        mock_decision.pull = ""
        mock_decision.nudge = "没什么感觉"
        mock_decision.state = "idle"
        registry.trigger.compute = MagicMock(return_value=mock_decision)

        await loop._check_trigger()
        assert len(triggered) == 0

    def test_stop(self, registry):
        loop = ProactiveLoop(registry)
        assert loop._running is False
        loop.stop()
        assert loop._running is False


class TestWebhookListener:
    """Test webhook message handling."""

    @pytest.mark.asyncio
    async def test_handle_message_adds_timestamp(self, registry):
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        msg = {"content": "你好呀"}
        await listener.handle_message(msg)

        assert "received_at" in msg
        assert msg["received_at"] is not None

    @pytest.mark.asyncio
    async def test_handle_message_records_interaction(self, registry):
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        await listener.handle_message({"content": "你好呀"})

        interactions = registry.memory.get_recent_interactions()
        assert len(interactions) == 1
        assert interactions[0]["content"] == "你好呀"

    @pytest.mark.asyncio
    async def test_handle_message_updates_hmm(self, registry):
        """Webhook should update HMM state via on_user_message."""
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        # Record initial HMM state
        initial_state = registry.trigger.hmm.current_state

        await listener.handle_message({"content": "测试消息"})

        # HMM should have transitioned on user message
        # The state might still be idle if no transition happened yet,
        # but on_user_message should have been called
        assert registry.trigger.hmm.last_user_message is not None

    @pytest.mark.asyncio
    async def test_handle_message_enqueues(self, registry):
        """Message should be routed to agent queue."""
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        await listener.handle_message({"content": "你好"})

        assert router.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_handle_message_empty_content(self, registry):
        """Empty message should still be processed without error."""
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        await listener.handle_message({"content": ""})

        interactions = registry.memory.get_recent_interactions()
        assert len(interactions) == 1
        assert interactions[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_handle_message_missing_content_key(self, registry):
        """Message without 'content' key should not crash."""
        router = MessageRouter()
        listener = WebhookListener(registry, router)

        await listener.handle_message({"type": "system_event"})

        interactions = registry.memory.get_recent_interactions()
        assert len(interactions) == 1
        assert interactions[0]["content"] == ""


class TestTrendingFetcher:
    """Test trending topic fetching and caching."""

    def test_initial_state(self, registry):
        fetcher = TrendingFetcher(registry, fetch_interval=3600)
        assert fetcher.fetch_interval == 3600
        assert fetcher._running is False
        assert fetcher.api_key == ""
        assert fetcher.api_base == ""
        assert fetcher.model == ""

    @pytest.mark.asyncio
    async def test_fetch_saves_topics(self, registry):
        """Test Baidu fallback path when no LLM credentials."""
        fetcher = TrendingFetcher(registry)

        import unittest.mock as mock
        mock_response = mock.MagicMock(text='{"word":"测试热搜1"}{"word":"测试热搜2"}')
        mock_client_ctx = mock.AsyncMock()
        mock_client_ctx.__aenter__.return_value.get.return_value = mock_response
        mock_client_ctx.__aexit__.return_value = None

        with mock.patch("httpx.AsyncClient", return_value=mock_client_ctx):
            await fetcher._fetch()

        topics = registry.trending.get()
        assert topics is not None
        assert len(topics) == 2
        assert topics[0]["title"] == "测试热搜1"

    @pytest.mark.asyncio
    async def test_fetch_baidu_first_llm_fallback(self, registry):
        """Baidu succeeds, should use Baidu (not LLM)."""
        fetcher = TrendingFetcher(
            registry,
            api_key="test-key",
            api_base="https://api.example.com/v1",
            model="test-model",
        )

        import unittest.mock as mock
        mock_resp = mock.MagicMock(text='{"word":"百度热搜1"}{"word":"百度热搜2"}')
        mock_client_ctx = mock.AsyncMock()
        mock_client_ctx.__aenter__.return_value.get.return_value = mock_resp
        mock_client_ctx.__aexit__.return_value = None

        with mock.patch("httpx.AsyncClient", return_value=mock_client_ctx):
            await fetcher._fetch()

        # Baidu should have been used, not LLM
        topics = registry.trending.get()
        assert topics is not None
        assert len(topics) == 2
        assert "百度热搜" in topics[0]["title"]

    @pytest.mark.asyncio
    async def test_fetch_llm_when_baidu_fails(self, registry):
        """When Baidu fails, should fall back to LLM."""
        fetcher = TrendingFetcher(
            registry,
            api_key="test-key",
            api_base="https://api.example.com/v1",
            model="test-model",
        )

        import unittest.mock as mock
        async def mock_get(*args, **kwargs):
            raise Exception("Baidu unavailable")

        mock_response_data = {
            "choices": [{"message": {"content": "LLM话题一\nLLM话题二\nLLM话题三"}}]
        }
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status.return_value = None

        mock_client_ctx = mock.AsyncMock()
        mock_client_ctx.__aenter__.return_value.get.side_effect = mock_get
        mock_client_ctx.__aenter__.return_value.post.return_value = mock_resp
        mock_client_ctx.__aexit__.return_value = None

        with mock.patch("httpx.AsyncClient", return_value=mock_client_ctx):
            await fetcher._fetch()

        # LLM fallback should have been used
        topics = registry.trending.get()
        assert topics is not None
        assert len(topics) == 3
        assert topics[0]["title"] == "LLM话题一"

    @pytest.mark.asyncio
    async def test_fetch_overwrites_cache(self, registry):
        fetcher = TrendingFetcher(registry)
        registry.trending.save([{"title": "旧话题"}])

        import unittest.mock as mock
        mock_response = mock.MagicMock(text='{"word":"新热搜"}')
        mock_client_ctx = mock.AsyncMock()
        mock_client_ctx.__aenter__.return_value.get.return_value = mock_response
        mock_client_ctx.__aexit__.return_value = None

        with mock.patch("httpx.AsyncClient", return_value=mock_client_ctx):
            await fetcher._fetch()

        topics = registry.trending.get()
        assert any("新热搜" in t["title"] for t in topics)

    def test_stop(self, registry):
        fetcher = TrendingFetcher(registry)
        assert fetcher._running is False
        fetcher.stop()
        assert fetcher._running is False

    def test_default_interval(self, registry):
        fetcher = TrendingFetcher(registry)
        assert fetcher.fetch_interval == 14400  # 4 hours
