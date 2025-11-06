"""Test loading MiniMax Search MCP Server from Git repository"""

import json
from pathlib import Path

import pytest

from mini_agent.tools.mcp_loader import cleanup_mcp_connections, load_mcp_tools_async


@pytest.fixture(scope="module")
def mcp_config():
    """Read MCP configuration"""
    mcp_config_path = Path("mini_agent/config/mcp.json")
    with open(mcp_config_path) as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_git_mcp_loading(mcp_config):
    """Test loading MCP Server from Git repository"""
    print("\n" + "=" * 70)
    print("Testing: Loading MiniMax Search MCP Server from Git repository")
    print("=" * 70)

    git_url = mcp_config["mcpServers"]["minimax_search"]["args"][1]
    print(f"\n📍 Git repository: {git_url}")
    print(f"⏳ Cloning and installing...\n")

    try:
        # Load MCP tools
        tools = await load_mcp_tools_async("mini_agent/config/mcp.json")

        print(f"\n✅ Loaded successfully!")
        print(f"\n📊 Statistics:")
        print(f"  • Total tools loaded: {len(tools)}")

        # Verify tools list is not empty
        assert isinstance(tools, list), "Should return a list of tools"

        if tools:
            print(f"\n🔧 Available tools:")
            for tool in tools:
                desc = (
                    tool.description[:80] + "..."
                    if len(tool.description) > 80
                    else tool.description
                )
                print(f"  • {tool.name}")
                print(f"    {desc}")

        # Verify expected tools
        expected_tools = ["search", "parallel_search", "browse"]
        loaded_tool_names = [t.name for t in tools]

        print(f"\n🔍 Function verification:")
        found_count = 0
        for expected in expected_tools:
            if expected in loaded_tool_names:
                print(f"  ✅ {expected} - OK")
                found_count += 1
            else:
                print(f"  ❌ {expected} - Missing")

        # If no expected tools found, minimax_search connection failed
        if found_count == 0:
            print(f"\n⚠️  Warning: minimax_search MCP Server connection failed")
            print(f"This may be due to SSH key authentication requirements or network issues")
            pytest.skip("minimax_search MCP Server connection failed, skipping test")

        # Assert all expected tools exist
        missing_tools = [t for t in expected_tools if t not in loaded_tool_names]
        assert len(missing_tools) == 0, f"Missing tools: {missing_tools}"

        print(f"\n" + "=" * 70)
        print("✅ All tests passed! MCP Server loaded from Git repository successfully!")
        print("=" * 70)

    finally:
        # Cleanup MCP connections to avoid async warnings
        print("\n🧹 Cleaning up MCP connections...")
        await cleanup_mcp_connections()


@pytest.mark.asyncio
async def test_git_mcp_tool_availability(mcp_config):
    """Test Git MCP tool availability"""
    print("\n=== Testing tool availability ===")

    try:
        tools = await load_mcp_tools_async("mini_agent/config/mcp.json")

        if not tools:
            pytest.skip("No MCP tools loaded")
            return

        # Find search tool
        search_tool = None
        for tool in tools:
            if "search" in tool.name.lower():
                search_tool = tool
                break

        assert search_tool is not None, "Should contain search-related tools"
        print(f"✅ Found search tool: {search_tool.name}")

    finally:
        await cleanup_mcp_connections()
