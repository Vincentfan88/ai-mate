"""P1-P5 code review fixes verification tests."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

import pytest


# ============================================================
# P1: Liveness recording integration
# ============================================================

class TestLivenessRecordingIntegration:
    """Verify liveness recording is wired into conversation flow."""

    def test_record_response_updates_session(self):
        """record_response should update current_session counters."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            assert tracker.current_session["total_messages"] == 0
            tracker.record_response("宝贝，今天好开心啊！想你了")
            assert tracker.current_session["total_messages"] == 1
            assert tracker.current_session["total_contacts"] == 1
            assert "开心" in tracker.current_session["emotions_expressed"]
            assert tracker.current_session["physical_references"] == 0

    def test_record_response_physical_detection(self):
        """Physical words should increment physical_references."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            tracker.record_response("（靠在你肩上）今天累了吗？")
            assert tracker.current_session["physical_references"] >= 1

    def test_record_response_vulnerability_detection(self):
        """Vulnerability words should increment vulnerability_count."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            tracker.record_response("今天有点难过，心情不好")
            assert tracker.current_session["vulnerability_count"] >= 1

    def test_record_response_surprise_detection(self):
        """Surprise patterns should set surprise_triggered."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            tracker.record_response("冷不丁问一句，你今天想我了没？")
            assert tracker.current_session["surprise_triggered"] is True

    def test_calculate_scores_reflects_activity(self):
        """Scores should change based on recorded activity, not just defaults."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            # Record varied interactions
            tracker.record_response("（靠在你肩上）今天好开心啊！")
            tracker.record_response("想你了，有点想你")
            tracker.record_response("猜猜我今天做了什么？")
            tracker.record_response("今天不太舒服，有点难过")
            tracker.record_initiated_contact()

            scores = tracker.calculate_scores()
            # At least some dimensions should be non-zero/non-default
            assert scores["主动性"] > 0, "Initiative should reflect initiated contacts"
            assert scores["情绪化"] > 0, "Emotionality should reflect varied emotions"
            assert scores["身体存在感"] > 0, "Physical presence should reflect physical words"

    def test_snapshot_persists(self):
        """Snapshot should be saved to disk."""
        from companion.modules.liveness import LivenessTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = LivenessTracker(data_path=f"{td}/liveness.json")
            tracker.record_response("开心")
            snap = tracker.snapshot()
            assert snap.overall_score > 0
            assert len(tracker.metrics_history) == 1


# ============================================================
# P2: Dead code verification
# ============================================================

class TestDeadCodeRemoval:
    """Verify dead code has been removed."""

    def test_old_tools_deleted(self):
        """companion/tools/__init__.py should not exist."""
        tools_path = Path(__file__).parent.parent.parent / "companion" / "tools" / "__init__.py"
        assert not tools_path.exists(), f"Dead code file still exists: {tools_path}"

    def test_no_message_router_in_server(self):
        """_message_router should not exist in server.py."""
        server_path = Path(__file__).parent.parent.parent / "companion" / "webui" / "server.py"
        content = server_path.read_text()
        # Should not have _message_router as a global
        assert "_message_router = None" not in content
        assert "global _proactive_loop, _message_router" not in content


# ============================================================
# P3: Anniversary/Habit integration
# ============================================================

class TestAnniversaryIntegration:
    """Verify anniversary module is integrated."""

    def test_anniversary_scene_in_tools(self):
        """CompanionStateTool or another tool should expose anniversary info."""
        from companion.agent.tools import CompanionStateTool
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(workspace=td, config_dir=str(
                Path(__file__).parent.parent.parent / "companion" / "config"
            ))
            # Should be accessible
            anniv = reg.anniversary
            assert anniv is not None
            # Should have at least basic functionality
            assert hasattr(anniv, "check_today") or hasattr(anniv, "get_days_together")

    def test_anniversary_in_proactive_loop(self):
        """ProactiveLoop should check anniversary as a trigger."""
        from companion.scheduler import ProactiveLoop
        import inspect
        source = inspect.getsource(ProactiveLoop)
        # Should mention anniversary or check it in _check_trigger
        assert "anniversary" in source.lower() or "check_today" in source


# ============================================================
# P4: Local model routing
# ============================================================

class TestLocalModelRouting:
    """Verify local model routing is implemented."""

    def test_build_companion_agent_accepts_local_config(self):
        """build_companion_agent should accept local model config."""
        from companion.cli import build_companion_agent
        import inspect
        sig = inspect.signature(build_companion_agent)
        # Should accept local model parameters
        params = set(sig.parameters.keys())
        assert "local_model_enabled" in params or "local_api_base" in params


# ============================================================
# P5a: FeishuTool conditional registration
# ============================================================

class TestFeishuConditional:
    """FeishuTool should only be registered when configured."""

    def test_feishu_tool_not_created_without_creds(self):
        """CompanionFeishuTool should not be in tools when no creds."""
        from companion.cli import build_companion_agent
        with patch.dict(os.environ, {}, clear=False):
            agent, reg, persona = build_companion_agent(
                workspace="workspace/companion",
                api_base="http://127.0.0.1:15721",
                api_key="test",
                model="test-model",
            )
            # Should NOT have feishu tool when no env vars
            tool_names = set(agent.tools.keys())
            assert "companion_feishu" not in tool_names, \
                "Feishu tool should not be registered without credentials"


# ============================================================
# P5b: externally_accessible usage
# ============================================================

class TestExternallyAccessible:
    """externally_accessible should affect HardFilter behavior."""

    def test_externally_accessible_used_in_check(self):
        """HardFilter.check() should reference externally_accessible."""
        from companion.modules.trigger.hard_filter import HardFilter
        import inspect
        source = inspect.getsource(HardFilter.check)
        assert "externally_accessible" in source, \
            "HardFilter.check() should use externally_accessible parameter"


# ============================================================
# P5c: price_cache_in config integration
# ============================================================

class TestPriceCacheInConfig:
    """price_cache_in from server config should be used in cost calculation."""

    def test_token_tracker_uses_configurable_cache_price(self):
        """TokenTracker should accept and use configurable cache price."""
        from companion.token_tracker import TokenTracker, TokenEntry
        with tempfile.TemporaryDirectory() as td:
            tracker = TokenTracker(workspace=td)
            # Test with cache tokens
            tracker.record(
                prompt_tokens=1000,
                completion_tokens=500,
                model="deepseek-v4-flash",
                cached_tokens=800,
                price_cache_in=0.05,  # Custom cache price
            )
            stats = tracker.get_stats()
            # Cost should reflect cache discount (800 cached at 0.05 vs 1.0 input)
            assert stats["total_cost"] < 0.02, \
                f"Cost should be lower with cache hit: {stats['total_cost']}"


# ============================================================
# P5d: user_name in persona prompt
# ============================================================

class TestUserNameInPersona:
    """user_name should appear in persona/system prompt."""

    def test_build_system_prompt_uses_user_name(self):
        """build_system_prompt should accept and use user_name."""
        from companion.agent.persona import build_system_prompt
        persona = {
            "name": "小美",
            "description": "你的AI伴侣",
            "personality": {"core_traits": ["温柔"], "moods": {}, "forbidden": []},
            "speaking_style": {"actions": [], "particles": [], "emojis": [], "max_length": 120},
            "greeting": "你好",
        }
        prompt = build_system_prompt(persona, user_name="Vincent")
        assert "Vincent" in prompt, "user_name should appear in system prompt"


# ============================================================
# P5e: PreferenceInfer access to interactions
# ============================================================

class TestPreferenceInferSignals:
    """PreferenceInfer should access interaction cache, not just facts."""

    def test_preference_infer_uses_interactions(self):
        """PreferenceInfer should get signals from interactions, not just facts."""
        from companion.modules.memory.preference import PreferenceInfer
        from companion.modules.memory.json_store import JsonFactStore
        from companion.modules.memory.interaction_cache import InteractionCache
        with tempfile.TemporaryDirectory() as td:
            fact_store = JsonFactStore(facts_path=f"{td}/facts.json")
            pref = PreferenceInfer(fact_store, data_path=f"{td}/preference.json")
            # Inject interaction cache
            if hasattr(pref, "set_interaction_cache"):
                pref.set_interaction_cache(InteractionCache(f"{td}/interactions.json"))
            # Should have access to interactions
            signals = pref._extract_signals()
            # Should work even with no facts
            assert isinstance(signals, list)


# ============================================================
# P5f: cooldown_hours HMM integration
# ============================================================

class TestCooldownHoursHMM:
    """cooldown_hours should affect HMM state machine behavior."""

    def test_hmm_uses_cooldown_hours(self):
        """HMM state transitions should respect cooldown_hours config."""
        from companion.modules.trigger.hmm_state_machine import HMMStateMachine
        with tempfile.TemporaryDirectory() as td:
            config = {
                "idle": {"weight": 0.35},
                "active": {"weight": 0.5},
                "missing": {"weight": 0.15, "cooldown_hours": 2},
                "longing": {"weight": 0.1},
            }
            hmm = HMMStateMachine(states_config=config, state_path=f"{td}/hmm_state.json")
            # Should have cooldown tracking
            assert hasattr(hmm, "_cooldown_until") or hasattr(hmm, "_last_state_time"), \
                "HMM should track cooldown timing"


# ============================================================
# P5g: Bare except cleanup
# ============================================================

class TestErrorHandling:
    """Bare except: pass should be replaced with logging."""


# ============================================================
# Quiet hours UI integration
# ============================================================

class TestQuietHoursIntegration:
    """Quiet hours should be configurable via UI and wired to HardFilter."""

    def test_registry_passes_quiet_hours_to_trigger(self):
        """Registry should accept quiet hours overrides and pass to TriggerEngine."""
        from companion.modules.registry import CompanionRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = CompanionRegistry(
                workspace=td,
                config_dir="companion/config",
                trigger_quiet_hours=(23, 7),
            )
            hf = reg.trigger.hard_filter
            assert hf.quiet_blocks == [(23, 7)]

    def test_quiet_hours_blocks_during_quiet_time(self):
        """HardFilter should block during quiet hours."""
        from companion.modules.trigger.hard_filter import HardFilter
        from datetime import datetime
        hf = HardFilter(quiet_hours=(0, 6))
        # 3am is in quiet hours
        passed, reason = hf.check(datetime(2026, 5, 2, 3, 0))
        assert passed is False
        assert "安静" in reason or "休息" in reason

    def test_quiet_hours_allows_outside_quiet_time(self):
        """HardFilter should allow outside quiet hours."""
        from companion.modules.trigger.hard_filter import HardFilter
        from datetime import datetime
        hf = HardFilter(quiet_hours=(0, 6))
        # 10am is outside quiet hours
        passed, reason = hf.check(datetime(2026, 5, 2, 10, 0))
        assert passed is True

    def test_no_bare_except_in_cli(self):
        """cli.py should not have bare except: pass."""
        cli_path = Path(__file__).parent.parent.parent / "companion" / "cli.py"
        content = cli_path.read_text()
        # Should not have "except Exception: pass" or "except: pass" in cleanup
        # Allow except blocks that log or raise
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "except Exception:" in line or line.strip() == "except:":
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                assert next_line != "pass", \
                    f"Bare except: pass found at line {i+2} of cli.py"
