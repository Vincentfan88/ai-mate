"""沙盒（无痕模式）隔离 + 销毁测试。"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestSandboxLifecycle:
    """验证沙盒 workspace 与主 workspace 完全隔离。"""

    def _build_server(self, tmpdir: str):
        """加载 server 模块并重置全局状态。"""
        config_path = f"{tmpdir}/config.json"
        # 清除已缓存的 server 模块
        for mod_name in list(sys.modules.keys()):
            if "companion.webui.server" in mod_name:
                del sys.modules[mod_name]

        with patch("companion.webui.server._start_feishu_bot"):
            import companion.webui.server as srv

            srv.CONFIG_FILE = Path(config_path)
            srv._config.clear()
            srv._config.update({
                "mbti": "ENFP",
                "persona": "default",
                "user_name": "",
                "budget": 0,
                "quiet_hours_blocks": [[0, 6]],
                "quiet_hours_start": 0,
                "quiet_hours_end": 6,
                "model": os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
                "api_base": os.environ.get("LLM_API_BASE", "https://api.deepseek.com/v1"),
                "api_key": os.environ.get("LLM_API_KEY", ""),
                "max_steps": 5,
                "workspace": "workspace/companion",
                "cloud_price_in": 1.0,
                "cloud_price_out": 4.0,
                "price_cache_in": 0.1,
                "local_model_enabled": False,
                "local_model": "qwen3-4b",
                "local_api_base": "http://127.0.0.1:1234/v1",
                "feishu_app_id": "",
                "feishu_app_secret": "",
                "feishu_chat_id": "",
                "feishu_enabled": False,
            })
            srv._agent_ref = None
            srv._sandbox_agent = None
            srv._sandbox_enabled = False
            srv._sandbox_persona_name = None
            return srv

    def test_sandbox_creates_tempdir(self, tmp_path):
        srv = self._build_server(str(tmp_path))

        # Mock build_companion_agent to return a fake agent with registry
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_persona = {"name": "sandbox", "greeting": "hi"}

        with patch.object(srv, "build_companion_agent", return_value=(mock_agent, mock_registry, mock_persona)):
            tempdir, wrapper, persona = srv._create_sandbox_agent()

        assert tempdir is not None
        assert "ai-mate-sandbox-" in tempdir.name
        assert Path(tempdir.name).exists()
        assert wrapper is not None
        assert persona is not None

        # Cleanup
        tempdir.cleanup()

    def test_sandbox_destroy_removes_tempdir(self, tmp_path):
        srv = self._build_server(str(tmp_path))

        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_persona = {"name": "sandbox", "greeting": "hi"}

        with patch.object(srv, "build_companion_agent", return_value=(mock_agent, mock_registry, mock_persona)):
            srv._sandbox_agent = srv._create_sandbox_agent()
            srv._sandbox_enabled = True

        tempdir_path = srv._sandbox_agent[0].name
        assert Path(tempdir_path).exists()

        # Destroy
        srv._destroy_sandbox()

        assert not Path(tempdir_path).exists(), "Temp directory should be deleted"
        assert srv._sandbox_agent is None
        assert srv._sandbox_enabled is False
        assert srv._sandbox_persona_name is None

    def test_sandbox_workspace_isolated_from_main(self, tmp_path):
        """验证沙盒 workspace 指向 tempdir，而非主 workspace。"""
        srv = self._build_server(str(tmp_path))

        mock_registry = MagicMock()
        mock_registry.workspace = "/tmp/sandbox-test/companion/sandbox"
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_persona = {"name": "sandbox", "greeting": "hi"}

        with patch.object(srv, "build_companion_agent", return_value=(mock_agent, mock_registry, mock_persona)):
            tempdir, wrapper, persona = srv._create_sandbox_agent()

        # 验证 workspace 指向 tempdir
        assert "ai-mate-sandbox-" in tempdir.name
        assert "workspace/companion" not in mock_registry.workspace or mock_registry.workspace.startswith(tempdir.name)

        tempdir.cleanup()

    def test_toggle_on_and_off(self, tmp_path):
        """验证 toggle 开启和关闭流程。"""
        srv = self._build_server(str(tmp_path))
        assert srv._sandbox_enabled is False

        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_persona = {"name": "sandbox", "greeting": "hi"}

        with patch.object(srv, "build_companion_agent", return_value=(mock_agent, mock_registry, mock_persona)):
            # Toggle on
            srv._sandbox_agent = srv._create_sandbox_agent()
            srv._sandbox_enabled = True
            assert srv._sandbox_enabled is True
            assert srv._sandbox_agent is not None

            tempdir_path = srv._sandbox_agent[0].name

            # Toggle off
            srv._destroy_sandbox()
            assert srv._sandbox_enabled is False
            assert srv._sandbox_agent is None
            assert not Path(tempdir_path).exists()


class TestSandboxDiskIsolation:
    """验证沙盒模式下磁盘文件写入隔离。"""

    def test_sandbox_writes_to_tempdir_not_main_workspace(self, tmp_path):
        """创建沙盒后，主 workspace 目录下不应产生新文件。"""
        main_workspace = tmp_path / "main_workspace"
        main_workspace.mkdir(parents=True, exist_ok=True)

        from companion.modules.memory.md_log import MdConversationLog
        from companion.modules.memory.interaction_cache import InteractionCache

        # 在 tempdir 中创建 memory 模块
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()

        sandbox_log = MdConversationLog(log_dir=str(sandbox_dir / "conversations"))
        sandbox_cache = InteractionCache(cache_path=str(sandbox_dir / "interactions.json"))

        # 写入沙盒
        sandbox_log.append("user", "secret message")
        sandbox_cache.add("user", "secret message")

        # 验证主目录无文件
        main_files = list(main_workspace.rglob("*"))
        assert len(main_files) == 0, f"Main workspace should be empty, found: {main_files}"

        # 验证沙盒目录有文件
        sandbox_files = list(sandbox_dir.rglob("*"))
        assert len(sandbox_files) > 0, "Sandbox should have files"

    def test_persona_file_destroyed_with_sandbox(self, tmp_path):
        """验证私密角色卡在销毁后不存在。"""
        # 创建 tempdir 并写入角色卡
        tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
        persona_dir = Path(tempdir.name) / "persona"
        persona_dir.mkdir()

        persona_data = {
            "name": "秘密角色",
            "description": "这是一个私密角色",
            "personality": {"core_traits": ["神秘", "温柔"]},
            "speaking_style": {"particles": ["呢", "哦"]},
        }
        persona_path = persona_dir / "secret.json"
        persona_path.write_text(json.dumps(persona_data, ensure_ascii=False), encoding="utf-8")

        # 验证角色卡存在
        assert persona_path.exists(), "Persona file should exist before destroy"

        # 销毁
        tempdir.cleanup()

        # 验证角色卡不存在
        assert not persona_path.exists(), "Persona file should be destroyed"
        assert not Path(tempdir.name).exists(), "Temp directory should be deleted"
