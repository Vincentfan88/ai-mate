"""PrideAxis — 用户主动频率轴，动态调节 connection 触发阈值。

pride 高 = 用户频繁主动来找我 → 安心 → 降低主动意愿
pride 低 = 用户很少来 → 不安 → 提高主动意愿
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class PrideAxis:
    """用户主动频率滑动平均。"""

    def __init__(
        self,
        state_path: str,
        growth_per_message: float = 0.30,
        decay_per_minute: float = 0.98,
        sensitivity: float = 0.30,
        base_threshold: float = 0.50,
    ):
        self.state_path = state_path
        self.growth_per_message = growth_per_message
        self.decay_per_minute = decay_per_minute
        self.sensitivity = sensitivity
        self.base_threshold = base_threshold

        # 内部状态
        self._value: float = 0.0
        self._last_decay_at: datetime = datetime.now()

        Path(state_path).parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def on_user_message(self, now: datetime | None = None) -> float:
        """用户主动发消息时，pride 增长。"""
        now = now or datetime.now()
        self._apply_decay(now)
        self._value = min(1.0, self._value + (1.0 - self._value) * self.growth_per_message)
        self._last_decay_at = now
        self._save_state()
        return self._value

    def get_pride(self, now: datetime | None = None) -> float:
        """获取当前 pride 值（应用衰减但不更新持久化）。"""
        now = now or datetime.now()
        value = self._decay_from_last(now)
        return max(0.0, min(1.0, value))

    def effective_threshold(self, now: datetime | None = None) -> float:
        """根据 pride 计算实际触发阈值。

        pride=0.0 → threshold = base - sensitivity * 0.5
        pride=0.5 → threshold = base
        pride=1.0 → threshold = base + sensitivity * 0.5
        """
        pride = self.get_pride(now)
        return self.base_threshold + (pride - 0.5) * self.sensitivity

    def get_state(self) -> dict:
        """返回状态快照。"""
        return {
            "pride": round(self._value, 3),
            "effective_threshold": round(self.effective_threshold(), 3),
            "base_threshold": self.base_threshold,
        }

    # ── 内部方法 ──

    def _decay_from_last(self, now: datetime) -> float:
        """从上次 decay 时间算衰减，返回衰减后的值（不修改内部状态）。"""
        elapsed_minutes = (now - self._last_decay_at).total_seconds() / 60.0
        if elapsed_minutes <= 0:
            return self._value
        return self._value * (self.decay_per_minute ** elapsed_minutes)

    def _apply_decay(self, now: datetime) -> None:
        """应用衰减到内部状态。"""
        elapsed_minutes = (now - self._last_decay_at).total_seconds() / 60.0
        if elapsed_minutes <= 0:
            return
        self._value = self._value * (self.decay_per_minute ** elapsed_minutes)

    # ── 持久化 ──

    def _load_state(self) -> None:
        path = Path(self.state_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._value = float(data.get("value", 0.0))
                if data.get("last_decay_at"):
                    self._last_decay_at = datetime.fromisoformat(data["last_decay_at"])
                else:
                    self._last_decay_at = datetime.now()
            except Exception as e:
                logger.warning(f"[PrideAxis] 加载状态失败: {e}")

    def _save_state(self) -> None:
        data = {
            "value": self._value,
            "last_decay_at": self._last_decay_at.isoformat(),
        }
        try:
            Path(self.state_path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[PrideAxis] 保存状态失败: {e}")
