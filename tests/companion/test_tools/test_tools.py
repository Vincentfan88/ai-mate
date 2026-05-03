"""Tests for registry and tool adapters."""

import asyncio
import tempfile

from companion.modules.registry import CompanionRegistry
from companion.agent.tools import (
    CompanionStateTool,
    CompanionMemoryTool,
    CompanionEmotionTool,
    CompanionTriggerTool,
    CompanionMBTITool,
    CompanionSceneTool,
    CompanionTrendingTool,
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
            tool = CompanionStateTool(reg)
            result = asyncio.run(tool.execute())
            assert "情绪" in result.content

    def test_memory_tool_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionMemoryTool(reg)
            result = asyncio.run(tool.execute(action="record", content="用户喜欢吃辣"))
            assert "已记录" in result.content

    def test_memory_tool_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            reg.memory.record("用户喜欢吃辣", importance=0.8)
            tool = CompanionMemoryTool(reg)
            result = asyncio.run(tool.execute(action="search", query="喜欢"))
            assert "记忆" in result.content

    def test_emotion_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionEmotionTool(reg)
            result = asyncio.run(tool.execute(event_type="user_message"))
            assert "情绪" in result.content

    def test_trigger_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionTriggerTool(reg)
            result = asyncio.run(tool.execute())
            assert "联系" in result.content

    def test_mbti_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionMBTITool(reg)
            result = asyncio.run(tool.execute(mbti_type="ENFP"))
            assert "ENFP" in result.content

    def test_scene_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionSceneTool(reg)
            result = asyncio.run(tool.execute(hour=8, mood="idle"))
            assert "场景" in result.content

    def test_trending_tool_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = make_registry(tmpdir)
            tool = CompanionTrendingTool(reg)
            result = asyncio.run(tool.execute())
            assert "暂无" in result.content or "话题" in result.content
