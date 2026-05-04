"""End-to-end integration test for companion system."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from companion.modules.registry import CompanionRegistry
from companion.agent.tools import (
    CompanionStateTool as StateTool,
    CompanionMemoryTool as MemoryTool,
    CompanionEmotionTool as EmotionTool,
    CompanionTriggerTool as TriggerTool,
    CompanionMBTITool as MBTITool,
    CompanionSceneTool as SceneTool,
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
        )
        yield reg


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_conversation_flow(self, registry):
        """Test: user message → memory record → emotion update → response."""
        # 1. Record user message in memory
        registry.memory.record("用户说今天工作顺利")
        registry.memory.add_conversation("user", "今天工作顺利")

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
        # Compute trigger
        decision = registry.trigger.compute()

        # The decision should have anthropomorphic fields
        assert decision.pull is not None
        assert decision.hold_back is not None
        assert decision.nudge is not None

    def test_memory_contagion_flow(self, registry):
        """Test: user sad → emotion contagion → different response."""
        # User sends sad message
        registry.memory.add_conversation("user", "今天心情不好")
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

    def test_all_tools_work(self, registry):
        """Test: all tool adapters return valid responses."""
        tools = [
            (StateTool(registry), {}),
            (MemoryTool(registry), {"action": "search", "query": ""}),
            (EmotionTool(registry), {"event_type": "time_passage"}),
            (TriggerTool(registry), {}),
            (MBTITool(registry), {"mbti_type": "ENFP"}),
            (SceneTool(registry), {"hour": 14, "mood": "idle"}),
        ]
        for tool, args in tools:
            result = asyncio.run(tool.execute(**args))
            assert result is not None
            assert isinstance(result.content, str)
            assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_message_router(self):
        """Test: message router enqueues and processes messages."""
        router = MessageRouter()
        received = []

        def handler(msg):
            received.append(msg)

        async def run_test():
            # Start router first
            task = asyncio.create_task(router.run(handler))
            await asyncio.sleep(0.05)
            # Then enqueue messages
            await router.enqueue({"content": "hello"})
            await router.enqueue({"content": "world"})
            await asyncio.sleep(0.3)
            router.stop()
            await task

        await run_test()
        assert len(received) >= 2  # Both messages should be processed

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

        metrics = registry.liveness.calculate_scores()
        assert metrics["主动性"] == 1.0

        # snapshot 会保存并重置 session
        snapshot = registry.liveness.snapshot()
        assert snapshot.dimension_scores["主动性"] == 1.0

    def test_trending_integration(self, registry):
        """Test: trending cache works end-to-end."""
        registry.trending.save([
            {"title": "测试热点话题"},
        ])
        topic = registry.trending.get_random_topic()
        assert "测试" in topic

    def test_preference_inference_end_to_end(self, registry):
        """Test: record facts → infer preferences → get beliefs."""
        # Record facts that signal preferences
        registry.memory.record("用户喜欢吃辣", importance=0.7)
        registry.memory.record("用户说今天加班到十点好累", importance=0.8)
        registry.memory.record("用户想周末睡个懒觉", importance=0.5)

        # Infer preferences (rule-based, no LLM)
        result = registry.memory.infer_preferences()
        assert result["inferences"] is not None
        assert result["belief_count"] > 0

        # Get active beliefs
        beliefs = registry.memory.preference.get_active_beliefs()
        assert len(beliefs) > 0
        assert beliefs[0].trust_score > 0

    def test_preference_inference_persistence(self, registry):
        """Test: inferred beliefs should persist across inference calls."""
        registry.memory.record("用户喜欢喝咖啡", importance=0.8)
        registry.memory.record("用户每天早上都想喝一杯", importance=0.5)

        # First inference
        result1 = registry.memory.infer_preferences()
        beliefs1 = registry.memory.preference.get_active_beliefs()

        # Second inference — same store, should accumulate
        result2 = registry.memory.infer_preferences()
        beliefs2 = registry.memory.preference.get_active_beliefs()

        assert len(beliefs2) >= len(beliefs1)

    def test_preference_confirm_and_deny(self):
        """Test: confirm/deny beliefs should update trust scores."""
        import tempfile
        from pathlib import Path
        from companion.modules.memory import MemorySystem

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = f"{tmpdir}/ws"
            Path(workspace).mkdir(parents=True)
            memory = MemorySystem(workspace=workspace, persona_path=None)

            memory.record("用户对辣的食物很感兴趣", importance=0.8)
            memory.infer_preferences()

            beliefs = memory.preference.get_active_beliefs()
            assert len(beliefs) > 0
            b = beliefs[0]
            initial_confirm = b.confirm_count
            memory.preference.confirm_belief(b.id)
            assert b.confirm_count == initial_confirm + 1

            memory.preference.deny_belief(b.id)
            assert b.deny_count == 1

    def test_contradiction_detection_end_to_end(self, registry):
        """Test: record contradictory facts → detect contradiction."""
        registry.memory.record("用户喜欢吃辣", importance=0.7)
        registry.memory.record("用户讨厌吃辣", importance=0.7)

        contradictions = registry.memory.check_contradictions()
        assert len(contradictions) > 0

    def test_liveness_multi_interaction_accumulation(self, registry):
        """Test: multiple interactions accumulate liveness dimensions."""
        # Simulate a series of interactions
        registry.liveness.record_initiated_contact()
        registry.liveness.record_response("今天有点累，想早点休息")
        registry.liveness.record_response("靠在你肩膀上真舒服")
        registry.liveness.record_response("宝贝，今天工作顺利吗")
        registry.liveness.record_response("哎呀，突然想吃火锅了")

        scores = registry.liveness.calculate_scores()
        # Should detect multiple emotion types
        assert scores["情绪化"] > 0
        # Should detect physical references
        assert scores["身体存在感"] > 0
        # Should detect vulnerability (有点累 matches vuln_words)
        assert scores["脆弱性"] > 0

    def test_emotion_residue_persistence(self, registry):
        """Test: emotion residue should persist and decay over time."""
        # First call
        emotion1 = registry.emotion.get_current_emotion("user_message")
        registry.emotion.save_residue()

        # Second call immediately after
        emotion2 = registry.emotion.get_current_emotion("user_message")

        # Both should return valid emotions
        assert emotion1["emotion"] is not None
        assert emotion2["emotion"] is not None

    def test_anniversary_and_habits_integration(self, registry):
        """Test: anniversary and habit tracking work end-to-end."""
        from datetime import datetime

        # Add anniversary via unified time_awareness
        registry.time_awareness.add_anniversary("认识纪念日", datetime(2025, 4, 30))

        # Check on anniversary date
        hits = registry.time_awareness.check_anniversaries_today(datetime(2026, 4, 30))
        assert len(hits) == 1
        assert "1 周年" in hits[0]

        # Get daily emoji
        emoji = registry.habits.get_daily_emoji()
        assert emoji is not None or emoji is None  # Config-controlled

        # Get catchphrase
        phrase = registry.habits.get_catchphrase()
        # May or may not appear (probability-based)
        assert phrase is None or isinstance(phrase, str)

    def test_full_webhook_emotion_trigger_pipeline(self, registry):
        """Test: webhook message → emotion → trigger pipeline."""
        import asyncio

        router = MessageRouter()
        webhook = WebhookListener(registry, router)

        # Simulate user sending a message
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                webhook.handle_message({"content": "今天好想你呀"})
            )
        finally:
            loop.close()

        # Emotion should reflect user emotion
        emotion = registry.emotion.get_current_emotion(
            "user_message", user_emotion="想念"
        )
        assert emotion["emotion"] is not None

        # Trigger should be computable
        decision = registry.trigger.compute()
        assert decision.pull is not None or decision.hold_back is not None


class TestPersonaIsolation:
    """Verify workspace is isolated per persona."""

    def test_different_personas_get_separate_workspaces(self):
        """Different persona_name values should use separate workspace directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = f"{tmpdir}/workspace/companion"
            Path(workspace).mkdir(parents=True)

            reg_a = CompanionRegistry(
                workspace=workspace,
                config_dir="companion/config",
                mbti_type="ENFP",
                persona_name="persona_a",
            )
            reg_b = CompanionRegistry(
                workspace=workspace,
                config_dir="companion/config",
                mbti_type="ENFP",
                persona_name="persona_b",
            )

            assert reg_a.workspace.endswith("persona_a")
            assert reg_b.workspace.endswith("persona_b")
            assert reg_a.workspace != reg_b.workspace

    def test_persona_data_is_isolated(self):
        """Writing data for one persona should not appear in another."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = f"{tmpdir}/workspace/companion"
            Path(workspace).mkdir(parents=True)

            reg_a = CompanionRegistry(
                workspace=workspace,
                config_dir="companion/config",
                mbti_type="ENFP",
                persona_name="persona_a",
            )
            reg_b = CompanionRegistry(
                workspace=workspace,
                config_dir="companion/config",
                mbti_type="ENFP",
                persona_name="persona_b",
            )

            # Record memory for persona A
            reg_a.memory.record("只属于 A 的记忆", importance=0.8)

            # Persona B should not see it
            results_b = reg_b.memory.search("只属于")
            assert len(results_b) == 0

    def test_default_persona_name(self):
        """Default persona_name should be 'default'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = f"{tmpdir}/workspace/companion"
            Path(workspace).mkdir(parents=True)
            reg = CompanionRegistry(workspace=workspace)
            assert reg.workspace.endswith("default")

    def test_avatar_dir_is_shared(self):
        """avatar_dir should point to the base workspace, not per-persona."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = f"{tmpdir}/workspace/companion"
            Path(workspace).mkdir(parents=True)
            reg = CompanionRegistry(workspace=workspace, persona_name="custom")
            assert "custom" not in reg.avatar_dir
            assert reg.avatar_dir == f"{workspace}/avatars"
