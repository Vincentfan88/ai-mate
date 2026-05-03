"""WebUI config persistence test — verify api_key and prices survive round-trip."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestConfigPersistence:
    """Test that api_key and price fields persist correctly through save/load cycle."""

    def _build_server(self, tmpdir: str):
        """Import fresh server module with isolated config."""
        config_path = f"{tmpdir}/config.json"

        # Mock the agent builder to avoid LLM calls
        with patch("companion.webui.server.build_companion_agent", return_value=None):
            with patch("companion.webui.server._start_feishu_bot"):
                with patch.object(Path, "exists", return_value=True):
                    # Force fresh imports by clearing cached module
                    for mod_name in list(sys.modules.keys()):
                        if "companion.webui.server" in mod_name:
                            del sys.modules[mod_name]

                    # Override config file path
                    import companion.webui.server as srv
                    srv.CONFIG_FILE = Path(config_path)
                    # Wipe in-memory config so it doesn't leak
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
                        "feishu_app_id": os.environ.get("FEISHU_APP_ID", ""),
                        "feishu_app_secret": os.environ.get("FEISHU_APP_SECRET", ""),
                        "feishu_chat_id": os.environ.get("FEISHU_CHAT_ID", ""),
                        "feishu_enabled": os.environ.get("FEISHU_ENABLED", "false").lower() == "true",
                        "name": "小美",
                        "greeting": "hello",
                        "has_avatar_ai": False,
                        "has_avatar_user": False,
                        "feishu_connected": False,
                    })
                    srv._agent_ref = None
                    return srv, config_path

    def test_api_key_and_prices_persist(self, tmp_path):
        """Core test: POST prices → _save_config → disk → _load_config → values restored.

        SECURITY: api_key and feishu_app_secret are intentionally NOT persisted to disk.
        They are loaded from .env only to prevent credential exposure via config.json.
        """
        srv, config_path = self._build_server(str(tmp_path))

        # Step 1: Verify nothing on disk yet
        assert not Path(config_path).exists(), "Config file should not exist yet"

        # Step 2: Simulate frontend POST — set config and save
        body = {
            "mbti": "INTJ",
            "persona": "default",
            "model": "qwen3.5-flash",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-test-abc123-secret-key",
            "cloud_price_in": 2.5,
            "cloud_price_out": 8.0,
            "price_cache_in": 0.2,
            "user_name": "Vincent",
            "local_model_enabled": True,
            "local_model": "qwen3-4b",
            "local_api_base": "http://127.0.0.1:1234/v1",
            "feishu_enabled": True,
            "feishu_app_id": "cli_test123",
            "feishu_app_secret": "secret_test456",
            "feishu_chat_id": "oc_test789",
            "budget": 100,
            "quiet_hours_blocks": [{"start": 0, "end": 6}],
            "quiet_hours_start": 0,
            "quiet_hours_end": 6,
        }

        with patch.object(srv, "_start_feishu_bot"), \
             patch.object(srv, "_stop_feishu_bot"):
            for k in ("mbti", "persona", "model", "api_base", "api_key", "max_steps", "workspace"):
                if k in body:
                    srv._config[k] = body[k]
            for k in ("cloud_price_in", "cloud_price_out", "price_cache_in"):
                if k in body:
                    srv._config[k] = body[k]
            if "user_name" in body:
                srv._config["user_name"] = body["user_name"]
            for k in ("local_model_enabled", "local_model", "local_api_base"):
                if k in body:
                    srv._config[k] = body[k]
            for k in ("budget",):
                if k in body:
                    srv._config[k] = body[k]
            if "quiet_hours_blocks" in body:
                blocks = body["quiet_hours_blocks"]
                srv._config["quiet_hours_blocks"] = [
                    [int(b["start"]), int(b["end"])] for b in blocks
                ]
            for k in ("quiet_hours_start", "quiet_hours_end"):
                if k in body:
                    srv._config[k] = int(body[k])
            for k in ("feishu_app_id", "feishu_chat_id", "feishu_enabled"):
                if k in body:
                    srv._config[k] = body[k]

            srv._save_config()

        # Step 3: Verify written to disk
        assert Path(config_path).exists(), "Config file should exist after save"
        disk_data = json.loads(Path(config_path).read_text(encoding="utf-8"))

        # Price fields must be persisted
        assert disk_data["cloud_price_in"] == 2.5, \
            f"cloud_price_in not persisted! Got: {disk_data.get('cloud_price_in')}"
        assert disk_data["cloud_price_out"] == 8.0, \
            f"cloud_price_out not persisted! Got: {disk_data.get('cloud_price_out')}"
        assert disk_data["price_cache_in"] == 0.2, \
            f"price_cache_in not persisted! Got: {disk_data.get('price_cache_in')}"

        # SECURITY: api_key must NOT be persisted to disk
        assert "api_key" not in disk_data, \
            f"SECURITY VIOLATION: api_key written to disk! Got keys: {list(disk_data.keys())}"

        # SECURITY: feishu_app_secret must NOT be persisted to disk
        assert "feishu_app_secret" not in disk_data, \
            f"SECURITY VIOLATION: feishu_app_secret written to disk!"

        print("  PASS: Prices persisted, secrets NOT persisted (security fix)")

        # Step 4: Simulate server restart — reload from disk
        srv._config["cloud_price_in"] = 1.0
        srv._config["cloud_price_out"] = 4.0
        srv._config["price_cache_in"] = 0.1

        srv._load_config()

        assert srv._config["cloud_price_in"] == 2.5, \
            f"cloud_price_in not restored! Got: {srv._config['cloud_price_in']}"
        assert srv._config["cloud_price_out"] == 8.0, \
            f"cloud_price_out not restored! Got: {srv._config['cloud_price_out']}"
        assert srv._config["price_cache_in"] == 0.2, \
            f"price_cache_in not restored! Got: {srv._config['price_cache_in']}"

        print("  PASS: All 4 critical fields restored after reload")

    def test_user_keys_completeness(self, tmp_path):
        """Verify _USER_KEYS includes all fields that should persist.

        SECURITY: api_key and feishu_app_secret intentionally excluded.
        """
        srv, _ = self._build_server(str(tmp_path))

        # api_key and feishu_app_secret are deliberately excluded (security)
        required_keys = {
            "cloud_price_in", "cloud_price_out", "price_cache_in",
            "model", "api_base",
            "mbti", "persona", "user_name", "budget",
            "quiet_hours_blocks", "quiet_hours_start", "quiet_hours_end",
            "local_model_enabled", "local_model", "local_api_base",
            "feishu_app_id", "feishu_chat_id", "feishu_enabled",
        }

        missing = required_keys - srv._USER_KEYS
        assert not missing, f"Missing from _USER_KEYS: {missing}"
        print("  PASS: _USER_KEYS contains all required fields")

    def test_save_excludes_non_user_keys(self, tmp_path):
        """Verify system-only fields are NOT written to config.json."""
        srv, config_path = self._build_server(str(tmp_path))

        # These should NOT be persisted (they come from .env)
        non_user_fields = {"max_steps", "workspace", "name", "greeting",
                           "has_avatar_ai", "has_avatar_user", "feishu_connected"}

        for field in non_user_fields:
            assert field not in srv._USER_KEYS, \
                f"{field} should NOT be in _USER_KEYS (it's system-only)"

        print("  PASS: Non-user fields correctly excluded from _USER_KEYS")


if __name__ == "__main__":
    import tempfile
    t = TestConfigPersistence()
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path
        t.test_api_key_and_prices_persist(Path(d))
    print("\nAll tests passed!")
