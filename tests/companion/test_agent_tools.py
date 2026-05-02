"""Mini-Agent Tool 适配器测试 — companion/agent/tools.py。"""

import pytest
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


@pytest.fixture
def registry():
    return CompanionRegistry(
        workspace="workspace/companion",
        config_dir="companion/config",
        mbti_type="ENFP",
    )


class TestCompanionAgentTools:
    """测试 Mini-Agent Tool 适配器层"""

    def test_state_tool_metadata(self, registry):
        tool = CompanionStateTool(registry)
        assert tool.name == "companion_state"
        assert tool.description
        assert tool.parameters == {"type": "object", "properties": {}}

    def test_state_tool_execute(self, registry):
        tool = CompanionStateTool(registry)

        import asyncio
        result = asyncio.run(tool.execute())
        assert result.success
        assert "当前状态" in result.content
        assert "情绪" in result.content
        assert "MBTI" in result.content

    def test_emotion_tool_metadata(self, registry):
        tool = CompanionEmotionTool(registry)
        assert tool.name == "companion_emotion"
        assert "event_type" in tool.parameters["properties"]
        assert "user_emotion" in tool.parameters["properties"]

    def test_emotion_tool_execute(self, registry):
        tool = CompanionEmotionTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(event_type="greeting"))
        assert result.success
        assert "当前情绪" in result.content

    def test_memory_tool_metadata(self, registry):
        tool = CompanionMemoryTool(registry)
        assert tool.name == "companion_memory"
        assert tool.parameters["required"] == ["action"]

    def test_memory_tool_search(self, registry):
        tool = CompanionMemoryTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(action="search", query="咖啡"))
        assert result.success

    def test_memory_tool_preferences(self, registry):
        tool = CompanionMemoryTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(action="preferences"))
        assert result.success

    def test_memory_tool_recent(self, registry):
        tool = CompanionMemoryTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(action="recent"))
        assert result.success

    def test_memory_tool_record_missing_content(self, registry):
        tool = CompanionMemoryTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(action="record"))
        assert not result.success
        assert "content" in result.error

    def test_trigger_tool_metadata(self, registry):
        tool = CompanionTriggerTool(registry)
        assert tool.name == "companion_trigger"
        assert "hours_since_last_contact" in tool.parameters["properties"]

    def test_trigger_tool_execute(self, registry):
        tool = CompanionTriggerTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(hours_since_last_contact=8))
        assert result.success
        assert "是否联系" in result.content

    def test_mbti_tool_metadata(self, registry):
        tool = CompanionMBTITool(registry)
        assert tool.name == "companion_mbti"
        assert "mbti_type" in tool.parameters["properties"]

    def test_mbti_tool_execute_default(self, registry):
        tool = CompanionMBTITool(registry)

        import asyncio
        result = asyncio.run(tool.execute())
        assert result.success
        assert "ENFP" in result.content

    def test_mbti_tool_execute_custom_type(self, registry):
        tool = CompanionMBTITool(registry)

        import asyncio
        result = asyncio.run(tool.execute(mbti_type="INTJ"))
        assert result.success
        assert "INTJ" in result.content

    def test_scene_tool_metadata(self, registry):
        tool = CompanionSceneTool(registry)
        assert tool.name == "companion_scene"
        assert "hour" in tool.parameters["properties"]
        assert "mood" in tool.parameters["properties"]

    def test_scene_tool_execute(self, registry):
        tool = CompanionSceneTool(registry)

        import asyncio
        result = asyncio.run(tool.execute(hour=20, mood="happy"))
        assert result.success

    def test_trending_tool_metadata(self, registry):
        tool = CompanionTrendingTool(registry)
        assert tool.name == "companion_trending"
        assert tool.parameters == {"type": "object", "properties": {}}

    def test_trending_tool_execute(self, registry):
        tool = CompanionTrendingTool(registry)

        import asyncio
        result = asyncio.run(tool.execute())
        assert result.success
