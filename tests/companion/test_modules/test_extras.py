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
        tracker = AnniversaryTracker(start_date=datetime(2025, 4, 30))
        tracker.add_anniversary("认识纪念日", datetime(2025, 4, 30))
        hits = tracker.check_today(datetime(2026, 4, 30))
        assert len(hits) == 1
        assert "1 周年" in hits[0]

    def test_no_anniversary(self):
        tracker = AnniversaryTracker(start_date=datetime(2025, 1, 1))
        hits = tracker.check_today(datetime(2026, 4, 30))
        assert len(hits) == 0

    def test_days_since_start(self):
        tracker = AnniversaryTracker(start_date=datetime(2026, 4, 20))
        days = tracker.days_since_start(datetime(2026, 4, 30))
        assert days == 10


class TestHabitTracker:
    """Test habit tracking."""

    def test_daily_emoji(self):
        tracker = HabitTracker(config_path="companion/config/habits.json")
        emoji = tracker.get_daily_emoji()
        assert emoji is None or len(emoji) >= 1

    def test_catchphrase(self):
        tracker = HabitTracker(config_path="companion/config/habits.json")
        phrase = tracker.get_catchphrase()
        assert phrase is None or isinstance(phrase, str)

    def test_add_habit(self):
        tracker = HabitTracker(config_path="companion/config/habits.json")
        tracker.add_habit("按时吃饭")
        assert "按时吃饭" in tracker.habits["daily"]


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
