"""触发引擎模块 — Weibull + HMM + HardFilter + 两阶段拟人化决策。"""

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .weibull import weibull_sample, compute_hour_bonus
from .hmm_state_machine import HMMState, HMMStateMachine
from .hard_filter import HardFilter


@dataclass
class TriggerDecision:
    """两阶段触发决策 — 拟人化输出"""
    should_trigger: bool
    pull: str            # "很想联系他的理由"
    hold_back: str       # "应该忍住的理由"
    nudge: str           # "冲动强度描述"
    state: str           # idle / missing / active


class TriggerEngine:
    """多层触发引擎 — 两阶段拟人化决策"""

    def __init__(self, config_path: str = "companion/config/triggers.json"):
        with open(config_path) as f:
            self.config = json.load(f)

        weibull_cfg = self.config["weibull"]
        self.alpha = weibull_cfg["alpha"]
        self.beta = weibull_cfg["beta"]

        hf_cfg = self.config["hard_filter"]
        self.hard_filter = HardFilter(
            quiet_hours=tuple(hf_cfg["quiet_hours"]),
            min_interval_hours=hf_cfg["min_interval_hours"],
            max_daily_contacts=hf_cfg["max_daily_contacts"],
            externally_accessible=hf_cfg.get("externally_accessible", True),
        )

        self.hmm = HMMStateMachine(self.config["states"])

    def compute(
        self,
        now: Optional[datetime] = None,
        hours_since_last_contact: Optional[float] = None,
    ) -> TriggerDecision:
        """
        计算触发决策（两阶段：计算 + 拟人化输出）

        Args:
            now: 当前时间
            hours_since_last_contact: 距离上次联系的小时数

        Returns:
            TriggerDecision
        """
        now = now or datetime.now()

        # === Stage 1: Numeric computation ===
        # 1. Hard filter
        passed, reason = self.hard_filter.check(now=now)
        if not passed:
            return TriggerDecision(
                should_trigger=False,
                pull="",
                hold_back=reason,
                nudge="none",
                state=self.hmm.current_state,
            )

        # 2. HMM state
        state = self.hmm.transition(now=now)
        state_weight = self.hmm.get_state_weight(state)

        # 3. Hour bonus
        hour = now.hour
        hour_bonus_val = compute_hour_bonus(hour, self.config["hour_bonus"])

        # 4. Weibull impulse
        sampled_interval = weibull_sample(self.alpha, self.beta)
        impulse_cfg = self.config["impulse"]
        if hours_since_last_contact is not None:
            # If we know the gap, compute impulse based on how long it's been
            impulse = min(1.0, hours_since_last_contact / self.beta)
        else:
            # Otherwise use the sampled interval to decide
            if sampled_interval <= 4:
                impulse = 0.8  # Short interval = strong impulse
            elif sampled_interval <= 12:
                impulse = 0.5
            else:
                impulse = 0.2

        # 5. Combined score
        impulse_weight = impulse_cfg.get("weight", 0.3)
        score = state_weight + hour_bonus_val + impulse * impulse_weight

        threshold_high = impulse_cfg.get("threshold_high", 0.55)
        threshold_low = impulse_cfg.get("threshold_low", 0.25)

        should_trigger = score >= threshold_low
        strong_trigger = score >= threshold_high

        # === Stage 2: Anthropomorphic output ===
        pull, hold_back, nudge = self._anthropomorphize(
            score=score,
            state=state,
            hour=hour,
            impulse=impulse,
            hours_since=hours_since_last_contact,
            strong=strong_trigger,
        )

        return TriggerDecision(
            should_trigger=should_trigger,
            pull=pull,
            hold_back=hold_back,
            nudge=nudge,
            state=state,
        )

    def _anthropomorphize(
        self,
        score: float,
        state: str,
        hour: int,
        impulse: float,
        hours_since: Optional[float],
        strong: bool,
    ) -> tuple[str, str, str]:
        """将数字转换为拟人化表达"""

        # Pull reasons
        pull_map = {
            "idle": ["有点想跟他说话", "想分享一点有趣的事给他", "不知道他在干嘛"],
            "missing": ["好想他呀", "感觉好久没联系了", "不知道他今天过得怎么样"],
            "active": ["刚才聊得挺开心的，想继续", "他还在跟我聊天呢"],
        }
        pulls = pull_map.get(state, pull_map["idle"])
        pull = random.choice(pulls)

        # Hold back reasons
        if 0 <= hour <= 6:
            hold_back = "这么晚了，他应该在休息"
        elif hour >= 22:
            hold_back = "夜深了，怕影响他睡觉"
        elif impulse < 0.3:
            hold_back = "好像也没什么特别的事"
        else:
            hold_back = random.choice([
                "也许他正在忙",
                "等他有空再找我也行",
                "不用每次都主动",
            ])

        # Nudge (impulse strength description)
        if score >= 0.7:
            nudge = "很想念"
        elif score >= 0.5:
            nudge = "有点想"
        elif score >= 0.3:
            nudge = "偶尔想起"
        else:
            nudge = "没什么感觉"

        return pull, hold_back, nudge
