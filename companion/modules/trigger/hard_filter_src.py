"""
硬规则过滤器 - Hard Rule Filter

实现触发前的基础过滤规则。
"""

from datetime import datetime
from typing import Optional, Dict, List, Callable
import logging

logger = logging.getLogger(__name__)


class HardRuleFilter:
    """硬规则过滤器 - 第 1 层过滤"""

    def __init__(
        self,
        quiet_hours: Optional[List[int]] = None,
        min_interval_hours: float = 4.0,
        max_daily_contacts: int = 20,
        do_not_disturb_times: Optional[Dict[str, List[int]]] = None
    ):
        """
        Args:
            quiet_hours: 安静时段列表（小时）
            min_interval_hours: 最小联系间隔（小时）
            max_daily_contacts: 每日最大联系次数
            do_not_disturb_times: DoNotDisturb 时间段配置 {date: [hours]}
        """
        self.quiet_hours = quiet_hours or list(range(0, 7))  # 默认凌晨 0-6 点
        self.min_interval_hours = min_interval_hours
        self.max_daily_contacts = max_daily_contacts
        self.do_not_disturb_times = do_not_disturb_times or {}

        self.last_contact_time: Optional[datetime] = None
        self.today_contact_count = 0

    def check(self, now: Optional[datetime] = None) -> tuple[bool, str]:
        """检查是否满足发送条件"""
        now = now or datetime.now()

        # 规则 1: 检查最后联系时间间隔
        if self.last_contact_time:
            hours_since = (now - self.last_contact_time).total_seconds() / 3600
            if hours_since < self.min_interval_hours:
                logger.debug(f"距离上次联系仅{hours_since:.1f}小时，未达到最小间隔")
                return False, "interval_too_short"

        # 规则 2: 检查是否在安静时段
        if now.hour in self.quiet_hours:
            logger.debug(f"当前是{now.hour}点，处于安静时段")
            return False, "quiet_hours"

        # 规则 3: 检查是否超出每日限制
        if self.today_contact_count >= self.max_daily_contacts:
            logger.debug(f"今日已联系{self.today_contact_count}次，达到上限")
            return False, "daily_limit_reached"

        # 规则 4: 检查 Do Not Disturb 设置
        dnd_hours = self.do_not_disturb_times.get(now.strftime("%Y-%m-%d"))
        if dnd_hours and now.hour in dnd_hours:
            logger.debug(f"{now.strftime('%Y-%m-%d')}设置了勿扰模式")
            return False, "do_not_disturb"

        logger.debug("通过所有硬规则检查")
        return True, "passed"

    def record_contact(self, timestamp: Optional[datetime] = None) -> None:
        """记录一次联系"""
        now = timestamp or datetime.now()

        # 检查是否是新的一天
        if not hasattr(self, '_current_date') or self._current_date != now.date():
            self._current_date = now.date()
            self.today_contact_count = 0

        self.today_contact_count += 1
        self.last_contact_time = now

    def set_quiet_hours(self, hours: list) -> None:
        """设置安静时段"""
        self.quiet_hours = hours
        logger.info(f"安静时段设置为：{hours}")

    def set_min_interval(self, hours: float) -> None:
        """设置最小联系间隔"""
        self.min_interval_hours = hours
        logger.info(f"最小联系间隔设置为：{hours}小时")

    def add_do_not_disturb(self, date: str, hours: list) -> None:
        """添加特定日期的勿扰时段"""
        self.do_not_disturb_times[date] = hours
        logger.info(f"添加了{date}的勿扰时段：{hours}")

    def clear_today_stats(self, target_date: Optional[datetime] = None) -> None:
        """重置今日的统计信息"""
        target_date = target_date or datetime.now()

        if not hasattr(self, '_current_date') or self._current_date == target_date.date():
            self.today_contact_count = 0
            self.last_contact_time = None
