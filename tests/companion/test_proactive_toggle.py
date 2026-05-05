"""Test the proactive/background loop toggle API."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestProactiveToggle:
    """Test /api/proactive/toggle endpoint."""

    def _build_server(self, tmpdir: str):
        """Import fresh server module with isolated config."""
        config_path = f"{tmpdir}/config.json"

        with patch("companion.webui.server.build_companion_agent", return_value=None):
            with patch("companion.webui.server._start_feishu_bot"):
                with patch.object(Path, "exists", return_value=False):
                    for mod_name in list(sys.modules.keys()):
                        if "companion.webui.server" in mod_name:
                            del sys.modules[mod_name]

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
                        "model": "deepseek-v4-flash",
                        "api_base": "https://api.deepseek.com/v1",
                        "api_key": "sk-test-key",
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
                        "proactive_enabled": True,
                        "name": "小美",
                        "greeting": "hello",
                        "has_avatar_ai": False,
                        "has_avatar_user": False,
                        "feishu_connected": False,
                    })
                    srv._agent_ref = None
                    srv._proactive_loop = None
                    srv._trending_fetcher = None
                    return srv, config_path

    def test_proactive_enabled_in_user_keys(self, tmp_path):
        """Verify proactive_enabled is in _USER_KEYS for persistence."""
        srv, _ = self._build_server(str(tmp_path))
        assert "proactive_enabled" in srv._USER_KEYS

    def test_proactive_enabled_persists(self, tmp_path):
        """Verify proactive_enabled survives save/load cycle."""
        srv, config_path = self._build_server(str(tmp_path))

        # Set to False and save
        srv._config["proactive_enabled"] = False
        srv._save_config()

        disk_data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        assert disk_data["proactive_enabled"] is False

        # Simulate restart: clear and reload
        srv._config["proactive_enabled"] = True
        srv._load_config()
        assert srv._config["proactive_enabled"] is False

    def test_toggle_disable_stops_loops(self, tmp_path):
        """Test disabling stops existing loops."""
        srv, _ = self._build_server(str(tmp_path))

        mock_loop = MagicMock()
        mock_fetcher = MagicMock()
        srv._proactive_loop = mock_loop
        srv._trending_fetcher = mock_fetcher

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            srv.toggle_proactive({"enabled": False})
        )

        assert result["status"] == "ok"
        assert result["enabled"] is False
        mock_loop.stop.assert_called_once()
        mock_fetcher.stop.assert_called_once()
        assert srv._proactive_loop is None
        assert srv._trending_fetcher is None
        assert srv._config["proactive_enabled"] is False

    def test_toggle_enable_starts_loops(self, tmp_path):
        """Test enabling creates new loops."""
        srv, _ = self._build_server(str(tmp_path))

        mock_loop = MagicMock()
        mock_fetcher = MagicMock()
        mock_registry = MagicMock()

        # Create a mock agent wrapper with registry
        mock_wrapper = MagicMock()
        mock_wrapper.registry = mock_registry
        srv._agent_ref = ("hash", mock_wrapper)

        import asyncio
        with patch("companion.scheduler.ProactiveLoop", return_value=mock_loop) as MockLoop, \
             patch("companion.scheduler.TrendingFetcher", return_value=mock_fetcher) as MockFetcher, \
             patch("asyncio.create_task"):

            result = asyncio.get_event_loop().run_until_complete(
                srv.toggle_proactive({"enabled": True})
            )

        assert result["status"] == "ok"
        assert result["enabled"] is True
        MockLoop.assert_called_once()
        MockFetcher.assert_called_once()
        assert srv._config["proactive_enabled"] is True

    def test_toggle_no_duplicate_start(self, tmp_path):
        """Test that enabling when already running returns early."""
        srv, _ = self._build_server(str(tmp_path))

        srv._proactive_loop = MagicMock()  # already running

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            srv.toggle_proactive({"enabled": True})
        )

        assert result["status"] == "ok"
        assert result["message"] == "后台循环已开启"

    def test_toggle_enable_without_registry(self, tmp_path):
        """Test enabling when agent is not available raises error and rolls back config."""
        srv, _ = self._build_server(str(tmp_path))

        srv._agent_ref = None
        srv._proactive_loop = None
        srv._config["proactive_enabled"] = True

        import asyncio
        # Re-patch build_companion_agent since the _build_server patch scope has exited
        with patch("companion.webui.server.build_companion_agent", return_value=None), \
             patch("companion.webui.server._get_or_create_agent", return_value=None):
            with pytest.raises(Exception):
                asyncio.get_event_loop().run_until_complete(
                    srv.toggle_proactive({"enabled": True})
                )

        # Config should be rolled back to False
        assert srv._config["proactive_enabled"] is False

    def test_proactive_config_in_update_config(self, tmp_path):
        """Test that update_config handles proactive_enabled from body."""
        srv, _ = self._build_server(str(tmp_path))

        with patch.object(srv, "_start_feishu_bot"), \
             patch.object(srv, "_stop_feishu_bot"):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                srv.update_config({"proactive_enabled": False})
            )

        assert result["status"] == "ok"
        assert srv._config["proactive_enabled"] is False


if __name__ == "__main__":
    import tempfile
    t = TestProactiveToggle()
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path
        t.test_proactive_enabled_in_user_keys(Path(d))
        t.test_proactive_enabled_persists(Path(d))
    print("\nAll tests passed!")
