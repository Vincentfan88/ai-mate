"""时间感知模块 — 统一管理时间事件 + 纪念日，支持自然日历解析。"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 支持的周期类型 ────────────────────────────────────────────

RECURRENCE_NONE = "none"
RECURRENCE_YEARLY = "yearly"
RECURRENCE_MONTHLY = "monthly"
RECURRENCE_WEEKLY = "weekly"


@dataclass
class TimeEvent:
    """一个时间事件/纪念日"""
    id: str
    content: str                    # 事件描述
    original_text: str              # 用户原话中的时间片段
    target_time: datetime           # 目标时间（纪念日用当年日期）
    status: str = "pending"         # pending / done / missed
    recurrence: str = RECURRENCE_NONE  # none / yearly / monthly / weekly
    created_at: str = ""
    is_anniversary: bool = False    # 是否为纪念日
    original_year: int = 0          # 纪念日原始年份（用于计算周年数）

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_time"] = self.target_time.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TimeEvent":
        d = dict(d)
        d["target_time"] = datetime.fromisoformat(d["target_time"])
        return cls(**d)

    def as_anniversary_text(self, now: Optional[datetime] = None) -> str:
        """返回纪念日展示文本"""
        now = now or datetime.now()
        if self.is_anniversary and self.recurrence == RECURRENCE_YEARLY and self.original_year > 0:
            years = now.year - self.original_year
            if years > 0:
                return f"{self.content} {years} 周年"
        return self.content


class TimeAwareness:
    """统一时间管理 — 提取用户消息中的时间事件 + 纪念日追踪。

    两种事件来源：
    1. 用户提及的未来事件（通过 extract_from_message 提取）
       → status pending → 到期触发提醒
    2. 纪念日/周年（通过 add_anniversary 添加）
       → 年度重复 → 每年当天触发

    所有事件统一持久化到 states/temporal_events.json。
    """

    def __init__(self, state_path: str = "workspace/companion/states/temporal_events.json"):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: List[TimeEvent] = []
        self._load_state()

    def _load_state(self):
        """从文件加载事件"""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                self._events = [TimeEvent.from_dict(d) for d in data]
            except Exception as e:
                logger.warning(f"[TimeAwareness] 加载状态失败: {e}")

    def _save_state(self):
        """保存事件到文件"""
        try:
            self.state_path.write_text(
                json.dumps([e.to_dict() for e in self._events], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[TimeAwareness] 保存状态失败: {e}")

    # ── 纪念日管理 ────────────────────────────────────────────

    def add_anniversary(self, name: str, date: datetime,
                        recurrence: str = RECURRENCE_YEARLY) -> TimeEvent:
        """添加纪念日（年度重复）"""
        # 使用当年的月日作为目标时间（便于每年检查）
        now = datetime.now()
        this_year = now.replace(month=date.month, day=date.day,
                                hour=9, minute=0, second=0, microsecond=0)
        if this_year < now:
            this_year = this_year.replace(year=now.year + 1)

        event = TimeEvent(
            id=f"ann_{len(self._events)}_{now.strftime('%Y%m%d%H%M%S')}",
            content=name,
            original_text=date.strftime("%m-%d"),
            target_time=this_year,
            status="pending",
            recurrence=recurrence,
            is_anniversary=True,
            original_year=date.year,
        )
        self._events.append(event)
        self._save_state()
        return event

    def check_anniversaries_today(self, now: Optional[datetime] = None) -> List[str]:
        """检查今天是否是某个纪念日，返回展示文本列表"""
        now = now or datetime.now()
        today_str = now.strftime("%m-%d")
        hits = []
        for ev in self._events:
            if ev.is_anniversary and ev.recurrence == RECURRENCE_YEARLY:
                if ev.target_time.strftime("%m-%d") == today_str:
                    hits.append(ev.as_anniversary_text(now=now))
        return hits

    def get_start_date(self) -> Optional[datetime]:
        """获取最早纪念日的原始日期（用于计算相识天数）"""
        anniversaries = [e for e in self._events if e.is_anniversary]
        if not anniversaries:
            return None
        # 返回排序后的第一个（最早期）
        anniversaries.sort(key=lambda e: (e.target_time.month, e.target_time.day))
        return anniversaries[0].target_time

    # ── 用户事件提取 ──────────────────────────────────────────

    def extract_from_message(self, message: str,
                            now: Optional[datetime] = None) -> Optional[TimeEvent]:
        """从用户消息中提取时间事件。"""
        now = now or datetime.now()
        match = self._match_time_expression(message, now)
        if not match:
            return None

        time_desc, target = match
        event = TimeEvent(
            id=f"te_{len(self._events)}_{now.strftime('%Y%m%d%H%M%S')}",
            content=message,
            original_text=time_desc,
            target_time=target,
            status="pending",
        )
        self._events.append(event)
        self._save_state()
        return event

    def check_pending(self, now: Optional[datetime] = None) -> List[TimeEvent]:
        """检查到期的 pending 事件，返回并标记为 missed。"""
        now = now or datetime.now()
        due_events = []
        for ev in self._events:
            if ev.status == "pending" and not ev.is_anniversary:
                if ev.target_time <= now:
                    ev.status = "missed"
                    due_events.append(ev)
        if due_events:
            self._save_state()
        return due_events

    def mark_done(self, event_id: str) -> bool:
        """标记某个事件为已完成"""
        for ev in self._events:
            if ev.id == event_id:
                ev.status = "done"
                self._save_state()
                return True
        return False

    def get_pending(self, now: Optional[datetime] = None) -> List[TimeEvent]:
        """获取所有仍为 pending 的非纪念日事件"""
        now = now or datetime.now()
        return [ev for ev in self._events
                if ev.status == "pending" and not ev.is_anniversary]

    def get_recent(self, limit: int = 5, now: Optional[datetime] = None) -> List[TimeEvent]:
        """获取最近的时间事件（用于注入对话上下文）"""
        now = now or datetime.now()
        pending = [ev for ev in self._events if ev.status == "pending" and not ev.is_anniversary]
        pending.sort(key=lambda e: e.target_time)
        return pending[:limit]

    def get_context_text(self, now: Optional[datetime] = None) -> str:
        """生成可读的时间事件上下文文本，用于注入 LLM prompt"""
        events = self.get_recent(now=now)
        if not events:
            return ""
        lines = ["[时间提醒]"]
        now = now or datetime.now()
        for ev in events:
            delta = (ev.target_time - now).total_seconds()
            if delta > 0:
                time_note = f"还有 {self._format_delta(delta)}"
            else:
                time_note = f"已过期 {self._format_delta(abs(delta))}"
            lines.append(f"- {ev.original_text}: {time_note}")
        return "\n".join(lines)

    def _format_delta(self, seconds: float) -> str:
        """格式化时间间隔"""
        days = seconds / 86400
        if days >= 1:
            return f"{int(days)} 天"
        hours = seconds / 3600
        if hours >= 1:
            return f"{int(hours)} 小时"
        minutes = seconds / 60
        return f"{int(minutes)} 分钟"

    def _advance_recurring_events(self, now: datetime) -> List[TimeEvent]:
        """推进已过期的年度事件到下一年（内部方法）"""
        triggered = []
        for ev in self._events:
            if ev.is_anniversary and ev.recurrence == RECURRENCE_YEARLY:
                if ev.target_time <= now and ev.status != "done":
                    # Advance to next occurrence
                    next_time = ev.target_time.replace(year=ev.target_time.year + 1)
                    ev.target_time = next_time
                    ev.status = "pending"
                    triggered.append(ev)
        if triggered:
            self._save_state()
        return triggered

    # ── 日期解析引擎 ──────────────────────────────────────────

    def _match_time_expression(self, message: str,
                               now: Optional[datetime] = None) -> Optional[tuple]:
        """从消息中匹配时间表达式，返回 (时间描述, target_datetime)。"""
        now = now or datetime.now()
        message_lower = message.lower()

        # ── 规则 1: 相对时间关键词 ──
        rules = [
            ("今晚", now.replace(hour=20, minute=0, second=0, microsecond=0)),
            ("晚上", now.replace(hour=20, minute=0, second=0, microsecond=0)),
            ("明天", now + timedelta(days=1)),
            ("明晚", now + timedelta(days=1) + timedelta(hours=20)),
            ("后天", now + timedelta(days=2)),
            ("大后天", now + timedelta(days=3)),
            ("这周末", now + timedelta(days=(5 - now.weekday()) % 7 or 7)),
            ("下周末", now + timedelta(days=(12 - now.weekday()) % 7)),
            ("下周", now + timedelta(days=7)),
            ("下个月", now + timedelta(days=30)),
            ("今天", now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)),
        ]
        for keyword, target in rules:
            if keyword in message_lower:
                return keyword, target

        # ── 规则 2: N天后/周后/月后 ──
        n_day_match = re.search(r'(\d+)\s*天[后以]', message)
        n_week_match = re.search(r'(\d+)\s*周[后以]', message)
        n_month_match = re.search(r'(\d+)\s*个?月[后以]', message)
        if n_day_match:
            n = int(n_day_match.group(1))
            target = now + timedelta(days=n)
            return f"{n}天后", target
        if n_week_match:
            n = int(n_week_match.group(1))
            target = now + timedelta(weeks=n)
            return f"{n}周后", target
        if n_month_match:
            n = int(n_month_match.group(1))
            target = now + timedelta(days=30 * n)
            return f"{n}个月后", target

        # ── 规则 3: 具体日期 MM月DD日 ──
        date_match = re.search(r'(\d{1,2})月(\d{1,2})[日号]?', message)
        if date_match:
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            year = now.year
            try:
                target = datetime(year, month, day)
                if target < now:
                    target = datetime(year + 1, month, day)
                return f"{month}月{day}日", target
            except ValueError:
                pass

        # ── 规则 4: 纯日期数字 5月20号 / 5.20 ──
        simple_date = re.search(r'(\d{1,2})[月.](\d{1,2})(号?)?', message)
        if simple_date:
            month = int(simple_date.group(1))
            day = int(simple_date.group(2))
            try:
                target = datetime(now.year, month, day)
                if target < now:
                    target = datetime(now.year + 1, month, day)
                return f"{month}月{day}日", target
            except ValueError:
                pass

        # ── 规则 5: 下周三 / 下周五 等星期偏移 ──
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 0, "天": 0}
        weekday_match = re.search(r'下(周)?([一二三四五六日天])', message_lower)
        if weekday_match:
            target_day = weekday_map.get(weekday_match.group(2))
            if target_day is not None:
                days_ahead = (target_day - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # 下周，而不是本周
                target = now + timedelta(days=days_ahead)
                day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                return f"下{day_names[target_day]}", target

        # ── 规则 6: 本周三 等当周星期 ──
        this_week_match = re.search(r'这(周|礼拜|周)?([一二三四五六日天])', message_lower)
        if this_week_match:
            target_day = weekday_map.get(this_week_match.group(2))
            if target_day is not None:
                days_ahead = (target_day - now.weekday()) % 7
                if days_ahead == 0:
                    target = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
                else:
                    target = now + timedelta(days=days_ahead)
                day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                return f"这{day_names[target_day]}", target

        return None