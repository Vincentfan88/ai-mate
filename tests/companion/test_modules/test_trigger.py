"""Tests for trigger module — ConnectionAxis + PrideAxis + Cooling + HMM + HardFilter."""

import json
import tempfile
from datetime import datetime, timedelta

from companion.modules.trigger import TriggerEngine
from companion.modules.trigger.connection_axis import ConnectionAxis
from companion.modules.trigger.pride_axis import PrideAxis


class TestConnectionAxis:
    """Test ConnectionAxis continuous growth model."""

    def test_initial_value(self):
        """New axis should start at initial_value."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json")
            assert axis.get_connection() == 0.0

    def test_tick_grows_over_time(self):
        """Connection should grow with elapsed time."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", growth_rate_per_hour=0.10)
            axis._initialized_at = datetime.now() - timedelta(hours=5)
            value = axis.tick()
            # 5h * 0.10 = 0.50, with ±10% noise → 0.45-0.55
            assert 0.35 <= value <= 0.65

    def test_tick_caps_at_max(self):
        """Connection should not exceed max_value."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", growth_rate_per_hour=0.10, max_value=1.0)
            axis._initialized_at = datetime.now() - timedelta(hours=20)
            value = axis.tick()
            assert value <= 1.0

    def test_sleep_growth_decelerated(self):
        """Connection should grow slower during quiet hours."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", growth_rate_per_hour=0.10)
            axis._initialized_at = datetime.now() - timedelta(hours=10)
            # At 3 AM (quiet hours): growth should be ×0.25
            value = axis.tick(now=datetime.now().replace(hour=3, minute=0), quiet_hours=(0, 6))
            # 10h * 0.10 * 0.25 = 0.25, with noise → roughly 0.2-0.3
            assert value <= 0.4

    def test_normal_growth_outside_quiet(self):
        """Connection should grow at full rate outside quiet hours."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", growth_rate_per_hour=0.10)
            axis._initialized_at = datetime.now() - timedelta(hours=10)
            # At 3 PM (not quiet): full growth
            value = axis.tick(now=datetime.now().replace(hour=15, minute=0), quiet_hours=(0, 6))
            # 10h * 0.10 = 1.0 (capped), with noise → roughly 0.9-1.0
            assert value >= 0.7

    def test_on_contact_resets_to_fixed_value(self):
        """on_contact should reset connection to contact_reset."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(
                state_path=f"{td}/conn.json",
                growth_rate_per_hour=0.10,
                contact_reset=0.40,
            )
            axis._initialized_at = datetime.now() - timedelta(hours=10)
            axis.tick()  # grow to ~1.0
            before = axis.get_connection()
            after = axis.on_contact()
            assert after == 0.40
            assert after < before

    def test_on_reply_drops_proportionally(self):
        """on_reply should drop connection by drop_fraction."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", growth_rate_per_hour=0.10)
            axis._initialized_at = datetime.now() - timedelta(hours=10)
            axis.tick()  # grow to ~1.0
            before = axis.get_connection()
            after = axis.on_reply()
            assert after < before
            # 40% drop: after ≈ before * 0.6
            assert after <= before * 0.65

    def test_on_reply_respects_min_value(self):
        """Connection should not drop below min_value."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", min_value=0.05)
            after = axis.on_reply()
            assert after >= 0.05

    def test_should_trigger(self):
        """should_trigger returns True when connection >= threshold."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", threshold=0.50)
            assert not axis.should_trigger()
            axis._value = 0.50
            assert axis.should_trigger()
            axis._value = 0.49
            assert not axis.should_trigger()

    def test_state_persists(self):
        """State should survive reload."""
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/conn.json"
            axis1 = ConnectionAxis(state_path=path, growth_rate_per_hour=0.10)
            axis1._initialized_at = datetime.now() - timedelta(hours=5)
            axis1.tick()
            axis1.on_contact()
            value_before = axis1.get_connection()

            axis2 = ConnectionAxis(state_path=path)
            assert abs(axis2.get_connection() - value_before) < 0.01

    def test_get_state_returns_snapshot(self):
        """get_state should return debug-friendly dict."""
        with tempfile.TemporaryDirectory() as td:
            axis = ConnectionAxis(state_path=f"{td}/conn.json", threshold=0.50)
            state = axis.get_state()
            assert "connection" in state
            assert "threshold" in state
            assert "should_trigger" in state
            assert "last_contact_at" in state
            assert "last_reply_at" in state


class TestPrideAxis:
    """Test PrideAxis — user-initiated message frequency."""

    def test_initial_pride_is_zero(self):
        """New pride should start at 0."""
        with tempfile.TemporaryDirectory() as td:
            pride = PrideAxis(state_path=f"{td}/pride.json")
            assert pride.get_pride() == 0.0

    def test_on_user_message_grows(self):
        """Pride should increase when user sends a message."""
        with tempfile.TemporaryDirectory() as td:
            pride = PrideAxis(state_path=f"{td}/pride.json", growth_per_message=0.30)
            v1 = pride.on_user_message()
            assert v1 == 0.30  # (1 - 0) * 0.30
            v2 = pride.on_user_message()
            assert v2 > v1
            assert v2 < 0.60  # diminishing returns

    def test_pride_caps_at_one(self):
        """Pride should not exceed 1.0."""
        with tempfile.TemporaryDirectory() as td:
            pride = PrideAxis(state_path=f"{td}/pride.json", growth_per_message=0.50)
            for _ in range(10):
                pride.on_user_message()
            assert pride.get_pride() <= 1.0

    def test_pride_decays_over_time(self):
        """Pride should decay over time."""
        with tempfile.TemporaryDirectory() as td:
            pride = PrideAxis(state_path=f"{td}/pride.json", decay_per_minute=0.90)
            pride.on_user_message()
            initial = pride.get_pride()
            # Simulate time passing
            future = pride._last_decay_at + timedelta(hours=2)
            decayed = pride.get_pride(now=future)
            assert decayed < initial

    def test_effective_threshold_increases_with_pride(self):
        """Higher pride → higher effective threshold (more restrained)."""
        with tempfile.TemporaryDirectory() as td:
            pride = PrideAxis(
                state_path=f"{td}/pride.json",
                growth_per_message=0.50,
                sensitivity=0.30,
                base_threshold=0.50,
            )
            # Low pride: threshold should be below base
            low_t = pride.effective_threshold()
            assert low_t <= 0.50

            # High pride after many messages
            for _ in range(5):
                pride.on_user_message()
            high_t = pride.effective_threshold()
            assert high_t > low_t

    def test_pride_persists(self):
        """Pride should survive reload."""
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/pride.json"
            p1 = PrideAxis(state_path=path, growth_per_message=0.30)
            p1.on_user_message()
            p1.on_user_message()
            v1 = p1.get_pride()

            p2 = PrideAxis(state_path=path)
            assert abs(p2.get_pride() - v1) < 0.01


class TestCooling:
    """Test cooling — AI should not trigger immediately after last contact."""

    def test_cooling_blocks_trigger_within_30_min(self):
        """Should not trigger within cooldown period."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # Simulate connection just triggered (last_contact_at = now - 10 min)
            engine.connection_axis.on_contact(now=datetime.now() - timedelta(minutes=10))
            # High connection, but within cooling period
            engine.connection_axis._value = 0.60
            decision = engine.compute()
            assert not decision.should_trigger
            assert "cooldown" in decision.nudge or "刚" in decision.hold_back

    def test_cooling_allows_after_30_min(self):
        """Should allow trigger after cooldown expires."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # last_contact_at = 35 min ago
            engine.connection_axis.on_contact(now=datetime.now() - timedelta(minutes=35))
            engine.connection_axis._value = 0.60
            decision = engine.compute()
            assert decision.should_trigger is True

    def test_cooling_configurable(self):
        """Cooldown duration should be configurable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir, cooldown_minutes=15)
            engine = TriggerEngine(config_path=config)
            # 20 min after contact with 15 min cooldown: should trigger
            engine.connection_axis.on_contact(now=datetime.now() - timedelta(minutes=20))
            engine.connection_axis._value = 0.60
            decision = engine.compute()
            assert decision.should_trigger is True


class TestIntegration:
    """Test pride + connection + cooling integration."""

    def test_on_user_message_updates_pride_and_connection(self):
        """on_user_message should update both pride and connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # Set connection high
            engine.connection_axis._value = 0.80
            before_pride = engine.pride_axis.get_pride()
            before_conn = engine.connection_axis.get_connection()

            engine.on_user_message()

            assert engine.pride_axis.get_pride() > before_pride
            assert engine.connection_axis.get_connection() < before_conn

    def test_praise_increases_threshold_making_trigger_harder(self):
        """High pride should make triggering harder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # Simulate high pride
            for _ in range(5):
                engine.pride_axis.on_user_message()

            threshold = engine.pride_axis.effective_threshold()
            # Should be higher than base
            assert threshold > engine.connection_axis.threshold


class TestHardFilter:
    """Test HardFilter rules."""

    def test_quiet_hours_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # 2 AM should be in quiet hours [0, 6]
            now = datetime.now().replace(hour=2, minute=0)
            decision = engine.compute(now=now)
            assert not decision.should_trigger
            assert "quiet" in decision.hold_back.lower() or "安静" in decision.hold_back or "晚" in decision.hold_back

    def test_multiple_quiet_hours_blocks(self):
        """Multiple quiet hour blocks should all block triggering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            config_data = json.load(open(config))
            # Add work hours block: 9-12 and 14-17
            config_data["hard_filter"]["quiet_hours"] = [[0, 6], [9, 12], [14, 17]]
            with open(config, "w") as f:
                json.dump(config_data, f)
            engine = TriggerEngine(config_path=config)

            # 2 AM: in [0, 6]
            now = datetime.now().replace(hour=2, minute=0)
            assert not engine.compute(now=now).should_trigger

            # 10 AM: in [9, 12]
            now = datetime.now().replace(hour=10, minute=0)
            assert not engine.compute(now=now).should_trigger

            # 3 PM: in [14, 17]
            now = datetime.now().replace(hour=15, minute=0)
            assert not engine.compute(now=now).should_trigger

            # 8 PM: not in any quiet block + connection high
            now = datetime.now().replace(hour=20, minute=0)
            engine.connection_axis._value = 0.60
            engine.connection_axis._last_contact_at = None
            assert engine.compute(now=now).should_trigger

    def test_long_gap_triggers(self):
        """After a long gap, connection should be high enough to trigger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # Simulate connection already high
            engine.connection_axis._value = 0.60
            # Clear cooling
            engine.connection_axis._last_contact_at = None
            now = datetime.now().replace(hour=21, minute=0)
            decision = engine.compute(now=now)
            assert decision.should_trigger is True
            assert decision.pull is not None
            assert len(decision.pull) > 0


class TestTriggerDecision:
    """Test TriggerDecision output format."""

    def test_decision_has_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            now = datetime.now().replace(hour=21, minute=0)
            decision = engine.compute(now=now)

            assert hasattr(decision, "should_trigger")
            assert hasattr(decision, "pull")
            assert hasattr(decision, "hold_back")
            assert hasattr(decision, "nudge")
            assert hasattr(decision, "state")
            assert hasattr(decision, "connection")
            assert 0 <= decision.connection <= 1.0

    def test_decision_state_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            now = datetime.now().replace(hour=14, minute=0)
            decision = engine.compute(now=now)
            assert decision.state in ("idle", "missing", "active")


class TestTriggerEngine:
    """Test full trigger engine integration."""

    def test_compute_returns_decision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            decision = engine.compute()
            assert decision is not None
            assert isinstance(decision.should_trigger, bool)


def _make_config(tmpdir: str, cooldown_minutes: int = 30) -> str:
    """Create a temporary config file for testing."""
    config = {
        "connection_axis": {
            "growth_rate_per_hour": 0.08,
            "threshold": 0.50,
            "contact_reset": 0.40,
            "drop_fraction": 0.4,
            "min_value": 0.05,
            "max_value": 1.0,
            "sleep_growth_multiplier": 0.25,
        },
        "pride_axis": {
            "growth_per_message": 0.30,
            "decay_per_minute": 0.98,
            "sensitivity": 0.20,
        },
        "cooling": {
            "contact_cooldown_minutes": cooldown_minutes,
        },
        "hard_filter": {
            "quiet_hours": [[0, 6]],
            "externally_accessible": True,
        },
        "states": {
            "idle": {"weight": 0.35},
            "missing": {"weight": 0.15, "cooldown_hours": 2},
            "active": {"weight": 0.05},
        },
    }
    path = f"{tmpdir}/triggers.json"
    with open(path, "w") as f:
        json.dump(config, f)
    return path
