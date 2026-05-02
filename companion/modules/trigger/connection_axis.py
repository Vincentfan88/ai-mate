"""ConnectionAxis — 连续积温轴，替代 Weibull 随机骰子。

connection 值随时间单调增长，主动联系后回落到固定值。
安静时段增长减速（模拟睡眠淡化但不遗忘）。
"""

import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionAxis:
    """连续积温轴 — 思念量随时间积累，联系后回落，睡眠减速。"""

    def __init__(
        self,
        state_path: str,
        growth_rate_per_hour: float = 0.08,
        threshold: float = 0.50,
        contact_reset: float = 0.40,
        drop_fraction: float = 0.4,
        min_value: float = 0.05,
        max_value: float = 1.0,
        initial_value: float = 0.0,
        sleep_growth_multiplier: float = 0.25,
    ):
        self.state_path = state_path
        self.growth_rate_per_hour = growth_rate_per_hour
        self.threshold = threshold
        self.contact_reset = contact_reset
        self.drop_fraction = drop_fraction
        self.min_value = min_value
        self.max_value = max_value
        self.initial_value = initial_value
        self.sleep_growth_multiplier = sleep_growth_multiplier

        # 内部状态
        self._value: float = initial_value
        self._last_contact_at: Optional[datetime] = None
        self._last_reply_at: Optional[datetime] = None
        self._initialized_at: Optional[datetime] = None
        self._last_tick_at: Optional[datetime] = None
        self._total_growth_cycles: int = 0

        # 自动创建父目录
        Path(state_path).parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    # ── 安静时段判断 ──

    @staticmethod
    def _is_in_quiet(hour: int, quiet_hours: tuple) -> bool:
        """判断当前小时是否在安静时段内。支持单段或多段。"""
        # 旧版单段: (start, end)
        if len(quiet_hours) == 2 and isinstance(quiet_hours[0], int):
            q_start, q_end = quiet_hours
            if q_start > q_end:  # 跨午夜，如 23-7
                return hour >= q_start or hour < q_end
            return q_start <= hour < q_end
        # 新版多段: [(start, end), ...]
        for block in quiet_hours:
            q_start, q_end = block
            if q_start > q_end:
                if hour >= q_start or hour < q_end:
                    return True
            else:
                if q_start <= hour < q_end:
                    return True
        return False

    # ── 核心方法 ──

    def tick(self, now: Optional[datetime] = None, quiet_hours: tuple = (0, 6)) -> float:
        """根据流逝时间推进 connection。返回当前值。

        安静时段增长减速（× sleep_growth_multiplier）。
        每次增长带 ±10% 随机噪声，防止精确可预测。
        """
        now = now or datetime.now()
        if self._initialized_at is None:
            self._initialized_at = now

        # 参考时间：从上次联系/回复开始积累；从未联系则从系统启动开始
        ref_time = self._last_contact_at or self._initialized_at

        # 首次 tick：初始化 _last_tick_at 并补回累积增长
        if self._last_tick_at is None:
            self._last_tick_at = ref_time
            delta_hours = (now - self._last_tick_at).total_seconds() / 3600.0
            if delta_hours > 0:
                # 大跨度（>1h）用中性倍率，避免安静时段倍率扭曲
                multiplier = 1.0 if delta_hours > 1.0 else self._get_growth_multiplier(now, quiet_hours)
                noise = random.uniform(-0.10, 0.10)
                growth = self.growth_rate_per_hour * delta_hours * multiplier * (1.0 + noise)
                self._value = min(self.max_value, max(self.min_value, self._value + growth))
            self._last_tick_at = now
            self._total_growth_cycles += 1
            self._save_state()
            return self._value

        # 常规 tick：增量增长
        delta_seconds = (now - self._last_tick_at).total_seconds()
        delta_hours = delta_seconds / 3600.0
        if delta_hours <= 0:
            return self._value

        multiplier = self._get_growth_multiplier(now, quiet_hours)
        noise = random.uniform(-0.10, 0.10)
        growth = self.growth_rate_per_hour * delta_hours * multiplier * (1.0 + noise)

        self._value = min(self.max_value, max(self.min_value, self._value + growth))
        self._last_tick_at = now
        self._total_growth_cycles += 1
        self._save_state()
        return self._value

    def on_contact(self, now: Optional[datetime] = None) -> float:
        """主动联系后 — 回落到固定值 contact_reset。"""
        now = now or datetime.now()
        self._value = self.contact_reset
        self._last_contact_at = now
        self._last_tick_at = now  # 防止瞬时重新触发
        self._save_state()
        return self._value

    def on_reply(self, now: Optional[datetime] = None) -> float:
        """用户回复 — 降低 connection（比例制）。"""
        now = now or datetime.now()
        self._value = max(self.min_value, self._value * (1.0 - self.drop_fraction))
        self._last_reply_at = now
        self._last_contact_at = now
        self._last_tick_at = now
        self._save_state()
        return self._value

    def should_trigger(self) -> bool:
        """是否达到触发阈值。"""
        return self._value >= self.threshold

    def get_connection(self) -> float:
        """返回当前 connection 值（不推进时间）。"""
        return self._value

    def reset(self) -> float:
        """重置为初始值。"""
        self._value = self.initial_value
        self._last_tick_at = None
        self._save_state()
        return self._value

    def get_state(self) -> dict:
        """返回当前状态快照（用于调试/工具展示）。"""
        return {
            "connection": round(self._value, 3),
            "threshold": self.threshold,
            "should_trigger": self.should_trigger(),
            "last_contact_at": self._last_contact_at.isoformat() if self._last_contact_at else None,
            "last_reply_at": self._last_reply_at.isoformat() if self._last_reply_at else None,
        }

    # ── 内部方法 ──

    def _get_growth_multiplier(self, now: datetime, quiet_hours: tuple) -> float:
        """根据当前小时返回增长倍率。"""
        if self._is_in_quiet(now.hour, quiet_hours):
            return self.sleep_growth_multiplier
        return 1.0

    # ── 持久化 ──

    def _load_state(self) -> None:
        """从文件恢复状态。"""
        path = Path(self.state_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._value = float(data.get("value", self.initial_value))
                if data.get("last_contact_at"):
                    self._last_contact_at = datetime.fromisoformat(data["last_contact_at"])
                if data.get("last_reply_at"):
                    self._last_reply_at = datetime.fromisoformat(data["last_reply_at"])
                if data.get("initialized_at"):
                    self._initialized_at = datetime.fromisoformat(data["initialized_at"])
                if data.get("last_tick_at"):
                    self._last_tick_at = datetime.fromisoformat(data["last_tick_at"])
                self._total_growth_cycles = int(data.get("total_growth_cycles", 0))
            except Exception as e:
                logger.warning(f"[ConnectionAxis] 加载状态失败: {e}")

    def _save_state(self) -> None:
        """保存状态到文件。"""
        data = {
            "value": self._value,
            "last_contact_at": self._last_contact_at.isoformat() if self._last_contact_at else None,
            "last_reply_at": self._last_reply_at.isoformat() if self._last_reply_at else None,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "last_tick_at": self._last_tick_at.isoformat() if self._last_tick_at else None,
            "total_growth_cycles": self._total_growth_cycles,
        }
        try:
            Path(self.state_path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[ConnectionAxis] 保存状态失败: {e}")
