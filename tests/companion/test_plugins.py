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