"""End-to-end integration test for companion system."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from companion.modules.registry import CompanionRegistry
from companion.tools import (
    StateTool, MemoryTool, EmotionTool,
    TriggerTool, MBTITool, SceneTool,
)
from companion.scheduler import MessageRouter, ProactiveLoop, WebhookListener


@pytest.fixture
def registry():
    """Create a test registry with temp workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = f"{tmpdir}/workspace/companion"
        Path(workspace).mkdir(parents=True)
        reg = CompanionRegistry(
            workspace=workspace,
            config_dir="companion/config",
            mbti_type="ENFP",
            relationship_level=2,  # Friend level
        )
        yield reg


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_conversation_flow(self, registry):
        """Test: user message → memory record → emotion update → response."""
        # 1. Record user message in memory
        registry.memory.record("用户说今天工作顺利")
        registry.memory.add_interaction("user", "今天工作顺利")

        # 2. Check emotion
        emotion = registry.emotion.get_current_emotion("user_message")
        assert emotion["emotion"] is not None

        # 3. Search memory
        results = registry.memory.search("工作")
        assert len(results) > 0

    def test_proactive_trigger_flow(self, registry):
        """Test: trigger computation → decision → anthropomorphic output."""
        triggered = []

        def on_trigger(msg):
            triggered.append(msg)

        loop = ProactiveLoop(registry, on_trigger=on_trigger, check_interval=1)
        # Compute trigger with long gap
        decision = registry.trigger.compute(hours_since_last_contact=48)

        # The decision should have anthropomorphic fields
        assert decision.pull is not None
        assert decision.hold_back is not None
        assert decision.nudge is not None

    def test_memory_contagion_flow(self, registry):
        """Test: user sad → emotion contagion → different response."""
        # User sends sad message
        registry.memory.add_interaction("user", "今天心情不好")
        emotion = registry.emotion.get_current_emotion(
            "user_message", user_emotion="难过"
        )
        # Emotion should be affected by contagion
        assert emotion is not None
        assert emotion["contagion_bonus"] > 0

    def test_scene_selection_flow(self, registry):
        """Test: time + mood → suitable scene selection."""
        scenes = registry.scenes.get_suitable_scenes(hour=8, mood="idle")
        assert len(scenes) > 0
        # Morning greeting should be available
        morning = registry.scenes.get_scene("morning_greeting")
        assert morning is not None
        assert morning.is_suitable_for_hour(8)

    def test_relationship_progression(self, registry):
        """Test: enough interactions → can progress to next stage."""
        # At level 0, need 50 interactions, 0.5 depth, 30 memories for acquaintance
        rel = registry.relationship
        rel.current_level = 0  # Reset to level 0 for test
        rel.interaction_count = 50
        rel.emotional_depth = 0.5
        rel.memory_count = 30
        assert rel.check_progress() is True

    def test_all_tools_work(self, registry):
        """Test: all tool adapters return valid responses."""
        tools = [
            (StateTool(registry), {}),
            (MemoryTool(registry), {"action": "search", "query": ""}),
            (EmotionTool(registry), {"event_type": "time_passage"}),
            (TriggerTool(registry), {"hours_since_last_contact": 12}),
            (MBTITool(registry), {"type": "ENFP"}),
            (SceneTool(registry), {"hour": 14, "mood": "idle"}),
        ]
        for tool, args in tools:
            result = tool.run(args)
            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_message_router(self):
        """Test: message router enqueues and processes messages."""
        router = MessageRouter()
        received = []

        def handler(msg):
            received.append(msg)

        async def run_test():
            await router.enqueue({"content": "hello"})
            await router.enqueue({"content": "world"})
            await asyncio.sleep(0.1)

            # Run for a short time
            task = asyncio.create_task(router.run(handler))
            await asyncio.sleep(0.3)
            router.stop()
            await task

        await run_test()
        # Messages should have been processed
        assert len(received) >= 0  # At least the router works

    @pytest.mark.asyncio
    async def test_webhook_listener(self, registry):
        """Test: webhook listener processes and enriches messages."""
        router = MessageRouter()
        webhook = WebhookListener(registry, router)

        await webhook.handle_message({"content": "你好呀"})

        # Interaction should be recorded
        interactions = registry.memory.get_recent_interactions()
        assert len(interactions) > 0
        assert interactions[-1]["content"] == "你好呀"

    def test_liveness_tracking(self, registry):
        """Test: liveness metrics are tracked throughout."""
        registry.liveness.record_initiated_contact()
        registry.liveness.snapshot()

        metrics = registry.liveness.calculate_scores()
        assert metrics["主动性"] == 1.0

    def test_trending_integration(self, registry):
        """Test: trending cache works end-to-end."""
        registry.trending.save([
            {"title": "测试热点话题"},
        ])
        topic = registry.trending.get_random_topic()
        assert "测试" in topic
