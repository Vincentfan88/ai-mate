"""Tests for companion plugin system."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from companion.plugins import load_plugin_tools, get_plugin_info


class TestPluginLoader:
    """Test the plugin loading mechanism."""

    def test_load_diary_plugin(self):
        """Should load the diary plugin from companion/plugins/."""
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(workspace=td, config_dir="companion/config")
            tools = load_plugin_tools(reg)
            assert len(tools) >= 1
            assert any(t.name == "companion_diary" for t in tools)

    def test_plugin_tool_has_name(self):
        """Loaded plugin tools should have a name property."""
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(workspace=td, config_dir="companion/config")
            tools = load_plugin_tools(reg)
            for tool in tools:
                assert tool.name
                assert isinstance(tool.name, str)

    def test_plugin_tool_has_description(self):
        """Loaded plugin tools should have a description property."""
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(workspace=td, config_dir="companion/config")
            tools = load_plugin_tools(reg)
            for tool in tools:
                assert tool.description
                assert isinstance(tool.description, str)

    def test_plugin_tool_has_parameters(self):
        """Loaded plugin tools should have a parameters schema."""
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(workspace=td, config_dir="companion/config")
            tools = load_plugin_tools(reg)
            for tool in tools:
                assert tool.parameters
                assert "type" in tool.parameters


class TestDiaryPlugin:
    """Test the diary plugin specifically."""

    def test_write_and_read_diary(self):
        """Should be able to write a diary entry and read it back."""
        import asyncio
        from companion.plugins.diary import CompanionDiaryTool
        with tempfile.TemporaryDirectory() as td:
            tool = CompanionDiaryTool(workspace=td)

            result = asyncio.run(tool.execute(
                action="write",
                content="今天很开心，和小美聊了很多",
                mood="happy",
            ))
            assert result.success

            result = asyncio.run(tool.execute(action="recent", limit=1))
            assert result.success
            assert "今天很开心" in result.content

    def test_write_twice_same_day_blocked(self):
        """Should not allow writing twice on the same day."""
        import asyncio
        from companion.plugins.diary import CompanionDiaryTool
        with tempfile.TemporaryDirectory() as td:
            tool = CompanionDiaryTool(workspace=td)

            asyncio.run(tool.execute(action="write", content="第一篇"))
            result = asyncio.run(tool.execute(action="write", content="第二篇"))
            assert not result.success
            assert "今天已经写过" in result.error

    def test_read_nonexistent_date(self):
        """Should return a friendly message for dates without entries."""
        import asyncio
        from companion.plugins.diary import CompanionDiaryTool
        with tempfile.TemporaryDirectory() as td:
            tool = CompanionDiaryTool(workspace=td)
            result = asyncio.run(tool.execute(action="read", date="2020-01-01"))
            assert result.success
            assert "没有日记" in result.content

    def test_empty_recent(self):
        """Should return a message when no entries exist."""
        import asyncio
        from companion.plugins.diary import CompanionDiaryTool
        with tempfile.TemporaryDirectory() as td:
            tool = CompanionDiaryTool(workspace=td)
            result = asyncio.run(tool.execute(action="recent"))
            assert result.success
            assert "还没有写过" in result.content

    def test_diary_persistence(self):
        """Diary entries should persist across tool restarts."""
        import asyncio
        from companion.plugins.diary import CompanionDiaryTool
        with tempfile.TemporaryDirectory() as td:
            tool1 = CompanionDiaryTool(workspace=td)
            asyncio.run(tool1.execute(action="write", content="持久化测试"))

            # New instance — should load persisted data
            tool2 = CompanionDiaryTool(workspace=td)
            result = asyncio.run(tool2.execute(action="recent"))
            assert result.success
            assert "持久化测试" in result.content


class TestDisabledPlugins:
    """Test that disabled plugins are not loaded."""

    def test_disabled_plugin_ignored(self):
        """Plugins ending in .disabled should not be loaded."""
        from companion.plugins import PLUGINS_DIR, load_plugin_tools
        from companion.modules.registry import CompanionRegistry

        # Create a fake disabled plugin
        disabled_dir = PLUGINS_DIR / "fake.disabled"
        disabled_dir.mkdir(exist_ok=True)
        (disabled_dir / "__init__.py").write_text(
            "def register(r): raise RuntimeError('should not load')\n"
        )

        try:
            with tempfile.TemporaryDirectory() as td:
                reg = CompanionRegistry(workspace=td, config_dir="companion/config")
                # Should not raise
                tools = load_plugin_tools(reg)
        finally:
            import shutil
            shutil.rmtree(disabled_dir, ignore_errors=True)