"""HMM 隐马尔可夫状态机 — 完整转移概率矩阵 + 外部因子驱动。"""

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("companion")


def _now_bj() -> datetime:
    """获取北京时间 (UTC+8) 的 naive datetime。"""
    utc_now = datetime.now(timezone.utc)
    return (utc_now.replace(tzinfo=None) + timedelta(hours=8))


class CompanionState:
    IDLE = "idle"
    ACTIVE = "active"
    MISSING = "missing"
    SHARE = "share"
    CHECKIN = "checkin"
    REFLECTIVE = "reflective"
    PLAYFUL = "playful"


# 完整状态转移概率矩阵
TRANSITION_PROBABILITIES = {
    CompanionState.IDLE: {
        CompanionState.ACTIVE: 0.60,
        CompanionState.MISSING: 0.25,
        CompanionState.SHARE: 0.10,
        CompanionState.CHECKIN: 0.05,
    },
    CompanionState.ACTIVE: {
        CompanionState.IDLE: 0.70,
        CompanionState.MISSING: 0.15,
        CompanionState.PLAYFUL: 0.10,
        CompanionState.REFLECTIVE: 0.05,
    },
    CompanionState.MISSING: {
        CompanionState.ACTIVE: 0.50,
        CompanionState.IDLE: 0.35,
        CompanionState.CHECKIN: 0.10,
        CompanionState.SHARE: 0.05,
    },
    CompanionState.SHARE: {
        CompanionState.ACTIVE: 0.40,
        CompanionState.IDLE: 0.45,
        CompanionState.PLAYFUL: 0.10,
        CompanionState.REFLECTIVE: 0.05,
    },
    CompanionState.CHECKIN: {
        CompanionState.ACTIVE: 0.45,
        CompanionState.IDLE: 0.50,
        CompanionState.MISSING: 0.05,
    },
    CompanionState.REFLECTIVE: {
        CompanionState.ACTIVE: 0.30,
        CompanionState.IDLE: 0.55,
        CompanionState.MISSING: 0.10,
        CompanionState.PLAYFUL: 0.05,
    },
    CompanionState.PLAYFUL: {
        CompanionState.ACTIVE: 0.50,
        CompanionState.IDLE: 0.40,
        CompanionState.SHARE: 0.05,
        CompanionState.CHECKIN: 0.05,
    },
}


def sample_next_state(current: str, exclude: List[str] = None) -> str:
    """根据转移概率采样下一状态"""
    exclude = exclude or []
    transitions = TRANSITION_PROBABILITIES.get(current, {})
    valid = {k: v for k, v in transitions.items() if k not in exclude}
    if not valid:
        return current

    states = list(valid.keys())
    probs = [valid[s] for s in states]
    total = sum(probs)
    probs = [p / total for p in probs]

    r = random.random()
    cumulative = 0.0
    for state, prob in zip(states, probs):
        cumulative += prob
        if r <= cumulative:
            return state
    return states[-1]


class StateHistory:
    """状态历史记录"""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.entries: List[Dict] = []

    def record(self, state: str, timestamp: datetime = None):
        self.entries.append({
            "state": state,
            "timestamp": (timestamp or _now_bj()).isoformat(),
        })
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def get_state_duration(self, state: str) -> Optional[float]:
        if not self.entries:
            return 0.0
        last = self.entries[-1]
        if last["state"] != state:
            return None
        last_time = datetime.fromisoformat(last["timestamp"])
        return (_now_bj() - last_time).total_seconds() / 3600


class HMMStateMachine:
    """HMM 隐马尔可夫模型状态机

    核心特性：
    - 完整转移概率矩阵（7 个状态）
    - 外部因子驱动（时间、联系间隔、用户活跃度）
    - 状态持久化
    """

    def __init__(self, states_config: dict = None, state_path: str = None):
        self.config = states_config or {}
        self.state_path = state_path

        self.current_state = CompanionState.IDLE
        self.state_history = StateHistory()
        self.state_entered_at: Optional[datetime] = None
        self.transition_count = 0
        self.last_user_message: Optional[datetime] = None
        self._last_state_time: Dict[str, datetime] = {}  # state -> last entered time
        self._cooldown_until: Dict[str, datetime] = {}   # state -> cooldown expiry

        # Ensure parent directory exists before any state operations
        if self.state_path:
            Path(self.state_path).parent.mkdir(parents=True, exist_ok=True)

        self._record_change(CompanionState.IDLE)
        self._load_state()

    def _load_state(self):
        """从文件恢复状态"""
        if self.state_path:
            try:
                data = json.loads(Path(self.state_path).read_text(encoding="utf-8"))
                self.current_state = data.get("state", CompanionState.IDLE)
                self.last_user_message = None
                if data.get("last_user_message"):
                    self.last_user_message = datetime.fromisoformat(data["last_user_message"])
                # Restore cooldown tracking
                for state_name, ts in data.get("last_state_times", {}).items():
                    try:
                        self._last_state_time[state_name] = datetime.fromisoformat(ts)
                    except ValueError:
                        pass
                for state_name, ts in data.get("cooldown_until", {}).items():
                    try:
                        self._cooldown_until[state_name] = datetime.fromisoformat(ts)
                    except ValueError:
                        pass
            except Exception as e:
                logger.warning(f"[HMM] 状态文件加载失败: {e}，使用默认状态")
                pass

    def _save_state(self):
        """保存状态到文件"""
        if self.state_path:
            data = {
                "state": self.current_state,
                "last_user_message": self.last_user_message.isoformat() if self.last_user_message else None,
                "transition_count": self.transition_count,
                "last_state_times": {k: v.isoformat() for k, v in self._last_state_time.items()},
                "cooldown_until": {k: v.isoformat() for k, v in self._cooldown_until.items()},
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

    def _record_change(self, new_state: str):
        self.current_state = new_state
        self.state_entered_at = _now_bj()
        self._last_state_time[new_state] = _now_bj()
        self.state_history.record(new_state)
        self.transition_count += 1
        self._save_state()

    def should_transition(
        self,
        hours_since_contact: float = None,
        hour_of_day: int = None,
    ) -> Tuple[bool, str]:
        """判断是否应该切换状态

        Args:
            hours_since_contact: 距上次联系的小时数
            hour_of_day: 当前小时

        Returns:
            (should_transition, target_state)
        """
        if hour_of_day is None:
            hour_of_day = _now_bj().hour

        # 规则 1: 长时间未联系 → 思念状态
        if hours_since_contact is not None:
            if hours_since_contact > 8 and self.current_state == CompanionState.IDLE:
                return True, CompanionState.MISSING

        # 规则 2: 深夜 → 内省模式 (10% 概率)
        if 22 <= hour_of_day <= 4 and self.current_state == CompanionState.IDLE:
            if random.random() < 0.1:
                return True, CompanionState.REFLECTIVE

        # 规则 3: 待机过长 → 统计转移
        if self.current_state == CompanionState.IDLE:
            idle_duration = self.state_history.get_state_duration(CompanionState.IDLE) or 0
            if idle_duration > 4:
                next_s = sample_next_state(
                    CompanionState.IDLE,
                    exclude=[CompanionState.ACTIVE],
                )
                return True, next_s

        return False, self.current_state

    def transition(self, now: datetime = None) -> str:
        """兼容旧接口的 transition 方法"""
        now = now or _now_bj()
        hours = None
        if self.last_user_message:
            hours = (now - self.last_user_message).total_seconds() / 3600

        should, target = self.should_transition(hours, now.hour)
        if should:
            # Check cooldown on target state
            if self._is_in_cooldown(target):
                return self.current_state
            self._record_change(target)
            self._apply_cooldown(target)
        return self.current_state

    def _is_in_cooldown(self, target_state: str) -> bool:
        """检查目标状态是否在冷却期内"""
        if target_state in self._cooldown_until:
            if _now_bj() < self._cooldown_until[target_state]:
                return True
        return False

    def _apply_cooldown(self, state: str) -> None:
        """对某个状态应用冷却时间"""
        from datetime import timedelta
        cooldown_hours = self.config.get(state, {}).get("cooldown_hours", 0)
        if cooldown_hours > 0:
            self._cooldown_until[state] = _now_bj() + timedelta(hours=cooldown_hours)

    def on_user_message(self, now: datetime = None):
        """用户发消息时切换到 active"""
        now = now or _now_bj()
        self.last_user_message = now
        self._record_change(CompanionState.ACTIVE)

    def exit_conversation(self) -> str:
        """退出对话，根据概率转移"""
        next_s = sample_next_state(CompanionState.ACTIVE, exclude=[CompanionState.ACTIVE])
        self._record_change(next_s)
        return self.current_state

    def get_state_weight(self, state: str = None) -> float:
        """获取当前状态权重"""
        state = state or self.current_state
        return self.config.get(state, {}).get("weight", 0.35)
