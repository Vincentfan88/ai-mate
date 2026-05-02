"""Tests for extras module — time context, anniversary, habits, trending."""

import json
import tempfile
from datetime import datetime, timedelta

from companion.modules.extras import (
    TimeContext,
    AnniversaryTracker,
    HabitTracker,
    TrendingCache,
)


class TestTimeContext:
    """Test time context generation."""

    def test_morning(self):
        ctx = TimeContext.from_now(datetime(2026, 4, 30, 8, 0))
        assert ctx.is_morning
        assert ctx.time_description == "上午"

    def test_night(self):
        ctx = TimeContext.from_now(datetime(2026, 4, 30, 23, 0))
        assert ctx.is_night
        assert ctx.time_description == "深夜"

    def test_weekend(self):
        # 2026-05-02 is Saturday
        ctx = TimeContext.from_now(datetime(2026, 5, 2, 12, 0))
        assert ctx.is_weekend

    def test_weekday(self):
        # 2026-04-30 is Thursday
        ctx = TimeContext.from_now(datetime(2026, 4, 30, 12, 0))
        assert not ctx.is_weekend


class TestAnniversaryTracker:
    """Test anniversary tracking."""

    def test_add_and_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/anniversaries.json"
            tracker = AnniversaryTracker(start_date=datetime(2025, 4, 30), state_path=state_path)
            tracker.add_anniversary("认识纪念日", datetime(2025, 4, 30))
            hits = tracker.check_today(datetime(2026, 4, 30))
            assert len(hits) == 1
            assert "1 周年" in hits[0]

    def test_no_anniversary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/anniversaries.json"
            tracker = AnniversaryTracker(start_date=datetime(2025, 1, 1), state_path=state_path)
            hits = tracker.check_today(datetime(2026, 4, 30))
            assert len(hits) == 0

    def test_days_since_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/anniversaries.json"
            tracker = AnniversaryTracker(start_date=datetime(2026, 4, 20), state_path=state_path)
            days = tracker.days_since_start(datetime(2026, 4, 30))
            assert days == 10

    def test_persistence(self):
        """Anniversary state should persist across restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/anniversaries.json"
            tracker = AnniversaryTracker(start_date=datetime(2025, 1, 1), state_path=state_path)
            tracker.add_anniversary("恋爱纪念日", datetime(2025, 4, 30))

            # New instance should load persisted state
            tracker2 = AnniversaryTracker(state_path=state_path)
            hits = tracker2.check_today(datetime(2026, 4, 30))
            assert len(hits) == 1
            assert "1 周年" in hits[0]


class TestHabitTracker:
    """Test habit tracking."""

    def test_daily_emoji(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/habits.json"
            tracker = HabitTracker(
                config_path="companion/config/habits.json",
                state_path=state_path,
            )
            emoji = tracker.get_daily_emoji()
            assert emoji is None or len(emoji) >= 1

    def test_catchphrase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/habits.json"
            tracker = HabitTracker(
                config_path="companion/config/habits.json",
                state_path=state_path,
            )
            phrase = tracker.get_catchphrase()
            assert phrase is None or isinstance(phrase, str)

    def test_add_habit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/habits.json"
            tracker = HabitTracker(
                config_path="companion/config/habits.json",
                state_path=state_path,
            )
            tracker.add_habit("按时吃饭")
            assert "按时吃饭" in tracker.habits["daily"]

    def test_daily_emoji_persistent(self):
        """Same day should return same emoji across restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/habits_state.json"
            now = datetime(2026, 5, 1, 10, 0)
            tracker = HabitTracker(
                config_path="companion/config/habits.json",
                state_path=state_path,
            )
            emoji1 = tracker.get_daily_emoji(now=now)

            # New instance — same day, same emoji
            tracker2 = HabitTracker(
                config_path="companion/config/habits.json",
                state_path=state_path,
            )
            emoji2 = tracker2.get_daily_emoji(now=now)
            assert emoji1 == emoji2


class TestTrendingCache:
    """Test trending cache."""

    def test_save_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TrendingCache(cache_path=f"{tmpdir}/trending.json")
            cache.save([{"title": "热搜第一"}, {"title": "热搜第二"}])
            items = cache.get()
            assert len(items) == 2
            assert items[0]["title"] == "热搜第一"

    def test_empty_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TrendingCache(cache_path=f"{tmpdir}/empty.json")
            assert cache.get() is None

    def test_random_topic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TrendingCache(cache_path=f"{tmpdir}/trending.json")
            cache.save([{"title": "话题A"}])
            topic = cache.get_random_topic()
            assert topic == "话题A"
