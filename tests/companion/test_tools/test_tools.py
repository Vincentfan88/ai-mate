"""Tests for registry and tool adapters."""

import tempfile

from companion.modules.registry import CompanionRegistry
from companion.tools import (
    StateTool, MemoryTool, EmotionTool,
    TriggerTool, MBTITool, SceneTool, TrendingTool,
)


def make_registry(tmpdir: str) -> CompanionRegistry:
    """Create a registry for testing."""
    import json
    import os

    # Ensure config exists
    config_dir = "companion/config"
    workspace = f"{tmpdir}/workspace/companion"
    os.makedirs(workspace)

    registry = CompanionRegistry(
        workspace=workspace,
        config_dir=config_dir,
        mbti_type="ENFP",
        relationship_level=0,
    )
    return registry


class TestRegistry:
    """Test companion registry."""

    def test_create_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            assert reg is not None

    def test_lazy_modules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            # Access lazy modules
            assert reg.memory is not None
            assert reg.emotion is not None
            assert reg.trigger is not None
            assert reg.mbti is not None
            assert reg.scenes is not None
            assert reg.relationship is not None
            assert reg.liveness is not None

    def test_get_module(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            _ = reg.memory  # Initialize
            assert reg.get_module("memory") is not None
            assert reg.get_module("nonexistent") is None


class TestTools:
    """Test tool adapters."""

    def test_state_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = StateTool(reg)
            result = tool.run({})
            assert "情绪" in result
            assert "关系" in result

    def test_memory_tool_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = MemoryTool(reg)
            result = tool.run({"action": "record", "content": "用户喜欢吃辣"})
            assert "已记录" in result

    def test_memory_tool_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            reg.memory.record("用户喜欢吃辣", importance=0.8)
            tool = MemoryTool(reg)
            result = tool.run({"action": "search", "query": "喜欢"})
            assert "记忆" in result

    def test_emotion_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = EmotionTool(reg)
            result = tool.run({"event_type": "user_message"})
            assert "情绪" in result

    def test_trigger_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = TriggerTool(reg)
            result = tool.run({"hours_since_last_contact": 24})
            assert "联系" in result

    def test_mbti_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = MBTITool(reg)
            result = tool.run({"type": "ENFP"})
            assert "ENFP" in result

    def test_scene_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = SceneTool(reg)
            result = tool.run({"hour": 8, "mood": "idle"})
            assert "场景" in result

    def test_trending_tool_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = TrendingTool(reg)
            result = tool.run({})
            assert "暂无" in result or "话题" in result
