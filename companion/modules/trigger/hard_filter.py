"""硬规则过滤器模块 — 安静时段/最小间隔/每日上限。"""

from datetime import datetime
from typing import Optional, Tuple


class HardFilter:
    """硬规则过滤器 — 第 1 层过滤"""

    def __init__(
        self,
        quiet_hours: tuple = (0, 6),
        min_interval_hours: float = 4.0,
        max_daily_contacts: int = 3,
        externally_accessible: bool = True,
    ):
        self.quiet_start, self.quiet_end = quiet_hours
        self.min_interval_hours = min_interval_hours
        self.max_daily_contacts = max_daily_contacts
        self.externally_accessible = externally_accessible

        self.last_contact_time: Optional[datetime] = None
        self.today_contact_count = 0
        self._current_date: Optional[datetime] = None

    def check(self, now: Optional[datetime] = None) -> Tuple[bool, str]:
        """检查是否满足发送条件

        Returns:
            (passed, reason)
        """
        now = now or datetime.now()
        self._reset_if_new_day(now)

        # 规则 1: 安静时段
        if self._is_quiet_hour(now.hour):
            return False, "现在是安静时段，应该让他好好休息"

        # 规则 2: 最小间隔
        if self.last_contact_time:
            hours_since = (now - self.last_contact_time).total_seconds() / 3600
            if hours_since < self.min_interval_hours:
                return False, f"距离上次联系时间太短，等一会儿再找他"

        # 规则 3: 每日上限
        if self.today_contact_count >= self.max_daily_contacts:
            return False, "今天已经联系过他了，明天再说吧"

        return True, "passed"

    def record_contact(self, timestamp: Optional[datetime] = None):
        """记录一次联系"""
        now = timestamp or datetime.now()
        self._reset_if_new_day(now)
        self.today_contact_count += 1
        self.last_contact_time = now

    def _is_quiet_hour(self, hour: int) -> bool:
        """判断是否在安静时段"""
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= hour <= self.quiet_end
        else:
            # Cross midnight (e.g., 23-7)
            return hour >= self.quiet_start or hour <= self.quiet_end

    def _reset_if_new_day(self, now: datetime):
        """如果是新的一天，重置今日计数"""
        today = now.date()
        if self._current_date != today:
            self._current_date = today
            self.today_contact_count = 0
