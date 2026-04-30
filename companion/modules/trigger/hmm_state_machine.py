"""HMM 状态机模块 — idle/missing/active 三状态。"""

from datetime import datetime
from typing import Optional


class HMMState:
    IDLE = "idle"
    MISSING = "missing"
    ACTIVE = "active"


class HMMStateMachine:
    """HMM 隐马尔可夫模型状态机"""

    def __init__(self, states_config: dict):
        """
        Args:
            states_config: {"idle": {"weight": 0.35}, "missing": {"weight": 0.15}, "active": {"weight": 0.05}}
        """
        self.config = states_config
        self.current_state = HMMState.IDLE
        self.last_user_message: Optional[datetime] = None

    def transition(self, now: Optional[datetime] = None) -> str:
        """根据时间推进状态"""
        now = now or datetime.now()

        if self.last_user_message:
            hours_since = (now - self.last_user_message).total_seconds() / 3600

            if hours_since < 2:
                self.current_state = HMMState.ACTIVE
            elif hours_since < self.config.get("missing", {}).get("cooldown_hours", 4):
                self.current_state = HMMState.MISSING
            else:
                self.current_state = HMMState.IDLE
        else:
            self.current_state = HMMState.IDLE

        return self.current_state

    def on_user_message(self, now: Optional[datetime] = None):
        """用户发消息时切换到 active"""
        self.last_user_message = now or datetime.now()
        self.current_state = HMMState.ACTIVE

    def get_state_weight(self, state: Optional[str] = None) -> float:
        """获取当前状态的权重"""
        state = state or self.current_state
        return self.config.get(state, {}).get("weight", 0.35)
