"""
HMM 状态机 - Hidden Markov Model State Machine

管理 AI 伴侣的不同行为状态及状态转移。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import random


class CompanionState(Enum):
    """AI 伴侣核心状态枚举"""

    IDLE = "idle"                      # 待机等待
    ACTIVE_CONVERSATION = "active"     # 正在聊天中
    MISSING_USER = "missing"           # 思念用户（长时间未联系）
    SHARE_MOMENT = "share"             # 分享当下（看到有趣事物）
    CHECK_IN = "checkin"               # 关心检查（特定时间/事件）
    REFLECTIVE = "reflective"          # 深夜内省模式
    PLAYFUL = "playful"                # 活泼调情模式


@dataclass
class StateConfig:
    """单个状态的配置"""
    base_weight: float = 0.2           # 基础权重（被选中的概率）
    min_interval_hours: float = 1.0    # 最小间隔时间
    max_duration_hours: float = 24.0   # 最大持续时长
    description: str = ""              # 状态描述


# 状态配置映射
STATE_CONFIGS: Dict[CompanionState, StateConfig] = {
    CompanionState.IDLE: StateConfig(
        base_weight=0.35,
        min_interval_hours=0.5,
        description="处于待机状态，等待触发或用户输入"
    ),
    CompanionState.ACTIVE_CONVERSATION: StateConfig(
        base_weight=0.40,
        min_interval_hours=0,
        description="正在与用户进行对话"
    ),
    CompanionState.MISSING_USER: StateConfig(
        base_weight=0.15,
        min_interval_hours=6.0,
        description="因为长时间未联系而思念用户"
    ),
    CompanionState.SHARE_MOMENT: StateConfig(
        base_weight=0.08,
        min_interval_hours=4.0,
        description="想分享当下的想法或见闻"
    ),
    CompanionState.CHECK_IN: StateConfig(
        base_weight=0.05,
        min_interval_hours=12.0,
        description="定期检查用户的状况"
    ),
    CompanionState.REFLECTIVE: StateConfig(
        base_weight=0.02,
        min_interval_hours=24.0,
        description="深夜时的内省和感性模式"
    ),
    CompanionState.PLAYFUL: StateConfig(
        base_weight=0.05,
        min_interval_hours=3.0,
        description="轻松活泼的调情互动"
    ),
}


class TransitionProbability:
    """状态转移概率矩阵"""

    # 定义合理的状态转移概率
    PROBABILITIES = {
        CompanionState.IDLE: {
            CompanionState.ACTIVE_CONVERSATION: 0.60,
            CompanionState.MISSING_USER: 0.25,
            CompanionState.SHARE_MOMENT: 0.10,
            CompanionState.CHECK_IN: 0.05,
        },
        CompanionState.ACTIVE_CONVERSATION: {
            CompanionState.IDLE: 0.70,
            CompanionState.MISSING_USER: 0.15,
            CompanionState.PLAYFUL: 0.10,
            CompanionState.REFLECTIVE: 0.05,
        },
        CompanionState.MISSING_USER: {
            CompanionState.ACTIVE_CONVERSATION: 0.50,
            CompanionState.IDLE: 0.35,
            CompanionState.CHECK_IN: 0.10,
            CompanionState.SHARE_MOMENT: 0.05,
        },
        CompanionState.SHARE_MOMENT: {
            CompanionState.ACTIVE_CONVERSATION: 0.40,
            CompanionState.IDLE: 0.45,
            CompanionState.PLAYFUL: 0.10,
            CompanionState.REFLECTIVE: 0.05,
        },
        CompanionState.CHECK_IN: {
            CompanionState.ACTIVE_CONVERSATION: 0.45,
            CompanionState.IDLE: 0.50,
            CompanionState.MISSING_USER: 0.05,
        },
        CompanionState.REFLECTIVE: {
            CompanionState.ACTIVE_CONVERSATION: 0.30,
            CompanionState.IDLE: 0.55,
            CompanionState.MISSING_USER: 0.10,
            CompanionState.PLAYFUL: 0.05,
        },
        CompanionState.PLAYFUL: {
            CompanionState.ACTIVE_CONVERSATION: 0.50,
            CompanionState.IDLE: 0.40,
            CompanionState.SHARE_MOMENT: 0.05,
            CompanionState.CHECK_IN: 0.05,
        },
    }

    @classmethod
    def get_transition_prob(cls, from_state: CompanionState, to_state: CompanionState) -> float:
        """获取从 from_state 转移到 to_state 的概率"""
        return cls.PROBABILITIES.get(from_state, {}).get(to_state, 0.0)

    @classmethod
    def sample_next_state(cls, current_state: CompanionState, exclude_states: List[CompanionState] = None) -> CompanionState:
        """根据转移概率采样下一个状态"""
        exclude_states = exclude_states or []

        transitions = cls.PROBABILITIES.get(current_state, {})
        valid_transitions = {k: v for k, v in transitions.items() if k not in exclude_states}

        if not valid_transitions:
            return current_state

        states = list(valid_transitions.keys())
        probs = [valid_transitions[s] for s in states]

        # 归一化概率
        total = sum(probs)
        probs = [p / total for p in probs]

        # 采样
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

    def record(self, state: CompanionState, timestamp: datetime = None) -> None:
        """记录状态变更"""
        entry = {
            "state": state.value,
            "timestamp": (timestamp or datetime.now()).isoformat(),
        }
        self.entries.append(entry)

        # 保持历史记录大小限制
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def get_recent_states(self, count: int = 10) -> List[Dict]:
        """获取最近的状态"""
        return self.entries[-count:]

    def get_state_duration(self, state: CompanionState) -> Optional[float]:
        """计算当前状态已持续的时长（小时）"""
        if not self.entries:
            return 0.0

        last_entry = self.entries[-1]
        if last_entry["state"] != state.value:
            return None

        last_time = datetime.fromisoformat(last_entry["timestamp"])
        duration = (datetime.now() - last_time).total_seconds() / 3600
        return duration


class HMMStateMachine:
    """隐马尔可夫模型状态机"""

    def __init__(self):
        self.current_state = CompanionState.IDLE
        self.state_history = StateHistory()
        self.state_entered_at: Optional[datetime] = None
        self.transition_count = 0

        # 初始化时记录首次进入 IDLE 状态
        self._record_state_change(CompanionState.IDLE)

    def _record_state_change(self, new_state: CompanionState) -> None:
        """内部方法：记录状态变更"""
        self.current_state = new_state
        self.state_entered_at = datetime.now()
        self.state_history.record(new_state)
        self.transition_count += 1

    def should_transition(self, external_factors: Optional[Dict] = None) -> tuple[bool, CompanionState]:
        """
        判断是否应该切换到其他状态

        Args:
            external_factors: 外部因素字典，包含：
                - hours_since_last_contact: 距上次联系的小时数
                - time_of_day: 一天中的时段 (0-23)
                - user_activity_level: 用户活跃度 (0-1)

        Returns:
            (should_transition, target_state)
        """
        external_factors = external_factors or {}

        # 因素 1: 长时间未联系 → 进入思念状态
        hours_since_contact = external_factors.get("hours_since_last_contact", 0)
        if hours_since_contact > 8 and self.current_state == CompanionState.IDLE:
            return True, CompanionState.MISSING_USER

        # 因素 2: 深夜时段 → 可能进入内省模式
        hour_of_day = external_factors.get("time_of_day", datetime.now().hour)
        if 22 <= hour_of_day <= 4 and self.current_state == CompanionState.IDLE:
            if random.random() < 0.1:  # 10% 概率
                return True, CompanionState.REFLECTIVE

        # 因素 3: 工作时间段 → 减少打扰
        if 9 <= hour_of_day <= 18 and self.current_state in [CompanionState.SHARE_MOMENT, CompanionState.PLAYFUL]:
            return False, CompanionState.IDLE

        # 因素 4: 基于历史记录的统计转移
        if self.current_state == CompanionState.IDLE:
            # 检查是否已达到某些状态的最大持续时间
            idle_duration = self.state_history.get_state_duration(CompanionState.IDLE) or 0
            if idle_duration > 4:  # 待机超过 4 小时
                next_state = TransitionProbability.sample_next_state(
                    CompanionState.IDLE,
                    exclude_states=[CompanionState.ACTIVE_CONVERSATION]  # 不能在对话中切换
                )
                return True, next_state

        return False, self.current_state

    def enter_conversation(self) -> None:
        """标记进入对话状态"""
        self._record_state_change(CompanionState.ACTIVE_CONVERSATION)

    def exit_conversation(self, user_feedback: Optional[str] = None) -> CompanionState:
        """
        标记退出对话状态，返回下一状态

        Args:
            user_feedback: 用户反馈（可选）

        Returns:
            下一状态
        """
        # 根据对话质量决定下一状态
        if user_feedback and len(user_feedback) > 50:
            # 长回复可能表示热情
            next_state = CompanionState.PLAYFUL if random.random() < 0.5 else CompanionState.IDLE
        else:
            next_state = CompanionState.IDLE

        self._record_state_change(next_state)
        return next_state

    def get_state_info(self) -> Dict:
        """获取当前状态的完整信息"""
        config = STATE_CONFIGS.get(self.current_state, StateConfig())
        duration = self.state_history.get_state_duration(self.current_state) or 0

        return {
            "state": self.current_state.value,
            "description": config.description,
            "base_weight": config.base_weight,
            "duration_hours": round(duration, 2),
            "min_interval": config.min_interval_hours,
            "transition_count": self.transition_count
        }

    def reset(self) -> None:
        """重置状态机"""
        self.current_state = CompanionState.IDLE
        self.state_history = StateHistory()
        self.state_entered_at = datetime.now()
        self.transition_count = 0
        self._record_state_change(CompanionState.IDLE)
