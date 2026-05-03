"""
Extras 模块 — 时间上下文 + 习惯 + 热搜缓存
时间事件 + 纪念日 → 统一使用 companion.modules.extras.time_awareness.TimeAwareness
"""

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .time_awareness import TimeAwareness, TimeEvent


@dataclass
class TimeContext:
    """时间上下文"""
    hour: int
    is_morning: bool
    is_afternoon: bool
    is_evening: bool
    is_night: bool
    is_weekend: bool
    time_description: str

    @classmethod
    def from_now(cls, now: Optional[datetime] = None) -> "TimeContext":
        now = now or datetime.now()
        hour = now.hour
        return cls(
            hour=hour,
            is_morning=6 <= hour < 12,
            is_afternoon=12 <= hour < 18,
            is_evening=18 <= hour < 22,
            is_night=22 <= hour or hour < 6,
            is_weekend=now.weekday() >= 5,
            time_description=_describe_time(hour),
        )


def _describe_time(hour: int) -> str:
    if 5 <= hour < 8:
        return "清晨"
    elif 8 <= hour < 12:
        return "上午"
    elif 12 <= hour < 14:
        return "中午"
    elif 14 <= hour < 18:
        return "下午"
    elif 18 <= hour < 22:
        return "晚上"
    else:
        return "深夜"


# AnniversaryTracker 已合并到 TimeAwareness，保留别名以兼容旧代码
# 实际使用: registry.time_awareness.add_anniversary() / check_anniversaries_today()
from .time_awareness import TimeAwareness as AnniversaryTracker  # noqa: F401


class HabitTracker:
    """习惯追踪 — 按日关联 emoji + 口头禅"""

    def __init__(self, config_path: str = "companion/config/habits.json",
                 state_path: str = "workspace/companion/habits_state.json"):
        self.config_path = config_path
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path) as f:
            self.config = json.load(f)

        self.habits: Dict[str, List[str]] = {"daily": [], "weekly": []}
        self._daily_emoji: Dict[str, str] = {}  # date -> emoji
        self._load_state()

    def _load_state(self):
        """加载习惯状态"""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                self._daily_emoji = data.get("daily_emoji", {})
            except Exception:
                pass

    def _save_state(self):
        """保存习惯状态"""
        data = {
            "daily_emoji": self._daily_emoji,
        }
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def add_habit(self, habit: str, frequency: str = "daily"):
        if frequency in self.habits:
            self.habits[frequency].append(habit)

    def get_daily_emoji(self, now: Optional[datetime] = None) -> Optional[str]:
        """获取今日 emoji — 按日期固定，非随机"""
        now = now or datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if today_str in self._daily_emoji:
            return self._daily_emoji[today_str]

        if not self.config.get("daily_emoji", {}).get("enabled"):
            return None

        emojis = ["😊", "🌟", "✨", "💕", "🌸", "🍀", "🌙"]
        chosen = random.choice(emojis)
        self._daily_emoji[today_str] = chosen
        self._save_state()
        return chosen

    def get_catchphrase(self) -> Optional[str]:
        """获取口头禅"""
        if not self.config.get("catchphrases", {}).get("enabled"):
            return None
        phrases = self.config["catchphrases"].get("list", [])
        if random.random() < self.config["catchphrases"].get("probability", 0.15):
            return random.choice(phrases)
        return None


class TrendingCache:
    """热搜缓存 — 定时预取 + 缓存注入"""

    def __init__(self, cache_path: str = "workspace/companion/trending_cache.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> Optional[List[dict]]:
        """获取缓存的热搜"""
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
            # Check if cache is stale (older than 4 hours)
            cached_at = datetime.fromisoformat(data["cached_at"])
            if (datetime.now() - cached_at).total_seconds() > 4 * 3600:
                return None
            return data.get("items", [])
        except Exception:
            return None

    def save(self, items: List[dict]):
        """保存热搜到缓存"""
        data = {
            "cached_at": datetime.now().isoformat(),
            "items": items,
        }
        self.cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_random_topic(self) -> Optional[str]:
        """随机获取一个话题"""
        items = self.get()
        if not items:
            return None
        item = random.choice(items)
        return item.get("title", item.get("text", ""))