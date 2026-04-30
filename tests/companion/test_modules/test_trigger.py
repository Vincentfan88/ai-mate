"""Tests for trigger module — Weibull, HMM, HardFilter, two-stage decision."""

import json
import tempfile
from datetime import datetime, timedelta

from companion.modules.trigger import TriggerEngine
from companion.modules.trigger.weibull import weibull_sample, compute_hour_bonus


class TestWeibull:
    """Test Weibull distribution sampling."""

    def test_weibull_returns_positive(self):
        """Weibull sample should always be positive."""
        for _ in range(10):
            result = weibull_sample(alpha=1.5, beta=12.0)
            assert result > 0

    def test_weibull_variance(self):
        """Different samples should produce different values."""
        results = [weibull_sample(alpha=1.5, beta=12.0) for _ in range(5)]
        # At least some variance
        assert len(set(round(r, 1) for r in results)) > 1

    def test_hour_bonus(self):
        """Evening hours should have highest bonus."""
        bonuses = {
            "morning": compute_hour_bonus(8, {"morning": 0.15, "noon": 0.25, "evening": 0.45, "night": 0.30}),
            "noon": compute_hour_bonus(13, {"morning": 0.15, "noon": 0.25, "evening": 0.45, "night": 0.30}),
            "evening": compute_hour_bonus(21, {"morning": 0.15, "noon": 0.25, "evening": 0.45, "night": 0.30}),
            "night": compute_hour_bonus(23, {"morning": 0.15, "noon": 0.25, "evening": 0.45, "night": 0.30}),
        }
        assert bonuses["evening"] >= bonuses["morning"]
        assert bonuses["evening"] >= bonuses["noon"]


class TestHardFilter:
    """Test HardFilter rules."""

    def test_quiet_hours_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # 2 AM should be in quiet hours [0, 6]
            now = datetime.now().replace(hour=2, minute=0)
            decision = engine.compute(now=now, hours_since_last_contact=48)
            assert not decision.should_trigger
            assert "quiet" in decision.hold_back.lower() or "安静" in decision.hold_back or "晚" in decision.hold_back

    def test_min_interval_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # Record a contact at 13:00, test at 14:00 (only 1 hour < 4 hour minimum)
            now = datetime.now().replace(hour=13, minute=0)
            engine.hard_filter.record_contact(now)
            test_now = now.replace(hour=14, minute=0)
            decision = engine.compute(now=test_now, hours_since_last_contact=1)
            assert not decision.should_trigger

    def test_long_gap_triggers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            # 48 hours since last contact, during good hours
            now = datetime.now().replace(hour=21, minute=0)
            decision = engine.compute(now=now, hours_since_last_contact=48)
            # Should have a strong pull to contact
            assert decision.pull is not None
            assert len(decision.pull) > 0


class TestTriggerDecision:
    """Test TriggerDecision output format."""

    def test_decision_has_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            now = datetime.now().replace(hour=21, minute=0)
            decision = engine.compute(now=now, hours_since_last_contact=24)

            assert hasattr(decision, "should_trigger")
            assert hasattr(decision, "pull")
            assert hasattr(decision, "hold_back")
            assert hasattr(decision, "nudge")
            assert hasattr(decision, "state")

    def test_decision_state_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(tmpdir)
            engine = TriggerEngine(config_path=config)
            now = datetime.now().replace(hour=14, minute=0)
            decision = engine.compute(now=now, hours_since_last_contact=24)
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


def _make_config(tmpdir: str) -> str:
    """Create a temporary config file for testing."""
    config = {
        "weibull": {"alpha": 1.5, "beta": 12.0},
        "hard_filter": {
            "quiet_hours": [0, 6],
            "min_interval_hours": 4,
            "max_daily_contacts": 3,
            "externally_accessible": True,
        },
        "states": {
            "idle": {"weight": 0.35},
            "missing": {"weight": 0.15, "cooldown_hours": 2},
            "active": {"weight": 0.05},
        },
        "hour_bonus": {
            "morning": 0.15,
            "noon": 0.25,
            "evening": 0.45,
            "night": 0.30,
        },
        "impulse": {
            "threshold_low": 0.25,
            "threshold_high": 0.55,
            "weight": 0.3,
        },
    }
    path = f"{tmpdir}/triggers.json"
    with open(path, "w") as f:
        json.dump(config, f)
    return path
