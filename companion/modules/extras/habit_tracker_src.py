"""
用户节律 & 习惯追踪系统

记录用户活跃规律，在习惯时段主动打招呼；
AI 能评论用户的日常规律，让互动更像老朋友。
"""

import json
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class HourlyActivity:
    """每小时活跃统计"""
    hour: int                    # 0-23
    message_count: int = 0       # 该小时的消息数
    last_seen: Optional[str] = None  # ISO 时间戳


@dataclass
class HabitPattern:
    """习惯模式"""
    peak_hours: List[int]        # 高活跃时段
    usual_sleep_hour: int        # 通常睡觉时间
    usual_wake_hour: int        # 通常起床时间
    weekdays_active: bool = True
    weekends_active: bool = True
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class UserHabitTracker:
    """
    追踪用户的活跃节律

    功能：
    - 记录每小时消息量，建立 HourlyActivity 档案
    - 计算峰值活跃时段
    - AI 在习惯时段主动打招呼时提及用户的规律
    - 判断当前是否是用户的"奇怪时间"（值得评论）
    """

    def __init__(self, data_path: str = "./data/habits"):
        self.data_path = data_path
        os.makedirs(self.data_path, exist_ok=True)
        self.hourly_counts: Dict[int, int] = defaultdict(int)
        self.last_seen: Dict[int, str] = {}
        self._load()

    def _file_path(self) -> str:
        return os.path.join(self.data_path, "user_habits.json")

    def _load(self):
        path = self._file_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.hourly_counts = defaultdict(int, data.get("hourly_counts", {}))
                self.last_seen = data.get("last_seen", {})
        except (json.JSONDecodeError, IOError):
            pass

    def _save(self):
        path = self._file_path()
        data = {
            "hourly_counts": dict(self.hourly_counts),
            "last_seen": self.last_seen,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"[HabitTracker] 保存失败: {e}")

    def record_activity(self, timestamp: Optional[datetime] = None) -> None:
        """记录一次活跃（用户发消息时调用）"""
        ts = timestamp or datetime.now()
        hour = ts.hour
        self.hourly_counts[hour] = self.hourly_counts.get(hour, 0) + 1
        self.last_seen[str(hour)] = ts.isoformat()
        self._save()

    def get_peak_hours(self, top_n: int = 3) -> List[int]:
        """
        获取最活跃的 N 个小时

        Returns:
            按活跃度降序的小时列表，如 [21, 14, 9]
        """
        if not self.hourly_counts:
            return []
        sorted_hours = sorted(
            self.hourly_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [h for h, _ in sorted_hours[:top_n]]

    def is_usual_active_hour(self, hour: Optional[int] = None) -> bool:
        """检查当前时间是否是用户习惯的活跃时段"""
        h = hour if hour is not None else datetime.now().hour
        if h not in self.hourly_counts:
            return False
        return self.hourly_counts[h] >= 2  # 至少发过2条消息

    def is_unusual_hour(self, hour: Optional[int] = None) -> bool:
        """
        检查当前时间是否是用户不常活动的时段
        AI 可以借此评论"你今天怎么这么早/晚"
        """
        h = hour if hour is not None else datetime.now().hour
        # 如果从未在这个小时活跃过，认为是 unusual
        if h not in self.hourly_counts:
            return True
        # 活跃度低于平均值的一半
        if not self.hourly_counts:
            return False
        avg = sum(self.hourly_counts.values()) / max(len(self.hourly_counts), 24)
        return self.hourly_counts[h] < avg * 0.3

    def get_habit_context(self) -> str:
        """
        生成习惯性上下文字符串

        Returns:
            如 "你一般在晚上9-11点比较活跃" 或 ""
        """
        peak = self.get_peak_hours(2)
        if not peak:
            return ""

        parts = []
        if len(peak) >= 2:
            sorted_peaks = sorted(peak)
            if sorted_peaks[1] - sorted_peaks[0] <= 2:
                parts.append(f"你一般晚上{sorted_peaks[0]}-{sorted_peaks[1]+1}点比较活跃")
            else:
                hours_str = "、".join(f"{h}:00" for h in sorted_peaks)
                parts.append(f"你在 {hours_str} 比较活跃")
        elif len(peak) == 1:
            parts.append(f"你一般{peak[0]}点左右比较活跃")

        return " ".join(parts) if parts else ""

    def get_unusual_comment(self) -> Optional[str]:
        """获取一条适合评论用户当前时段异常的话语"""
        if self.is_unusual_hour():
            hour = datetime.now().hour
            if hour < 8:
                return "你今天起这么早呀？难得难得 😊"
            elif hour > 23:
                return "这么晚了还在呀，注意休息哦 🌙"
            else:
                return "今天怎么这个时间还在，好少见呀"
        return None

    def get_habit_greeting(self) -> str:
        """
        基于习惯时段生成招呼语

        Returns:
            如 "你这个时候一般都在忙，我就不打扰了～" 或 ""
        """
        peak = self.get_peak_hours(1)
        if not peak:
            return ""
        usual = peak[0]
        now = datetime.now().hour
        diff = abs(now - usual)
        if diff >= 4 and self.hourly_counts.get(now, 0) < 1:
            if usual > 12 and now < usual:
                return f"这个点你一般还没上线，我就不打扰啦～"
            elif usual < 21 and now > usual:
                return f"你这个时候一般都在忙，我就不打扰了～"
        return ""