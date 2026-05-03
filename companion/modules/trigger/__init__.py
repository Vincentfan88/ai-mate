"""触发引擎模块 — ConnectionAxis + PrideAxis + Cooling + HMM + HardFilter + 两阶段拟人化决策。"""

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .connection_axis import ConnectionAxis
from .pride_axis import PrideAxis
from .hmm_state_machine import CompanionState, HMMStateMachine
from .hard_filter import HardFilter

logger = logging.getLogger(__name__)


def _derive_state_path(state_path: Optional[str], name: str) -> Optional[str]:
    """从 trigger_state 路径派生同目录的其他状态文件路径。"""
    if state_path:
        return str(Path(state_path).with_name(f"{name}.json"))
    return None


@dataclass
class TriggerDecision:
    """两阶段触发决策 — 拟人化输出"""
    should_trigger: bool
    pull: str            # "很想联系他的理由"
    hold_back: str       # "应该忍住的理由"
    nudge: str           # "冲动强度描述"
    state: str           # idle / missing / active
    connection: float    # connection axis value


class TriggerEngine:
    """多层触发引擎 — 两阶段拟人化决策

    决策流程:
    1. HardFilter (安静时段)
    2. ConnectionAxis (思念积累) + PrideAxis (用户主动频率)
    3. connection >= effective_threshold 则触发
    4. 触发后 connection 回落（connection 自然增长实现间隔）
    """

    def __init__(
        self,
        config_path: str = "companion/config/triggers.json",
        state_path: Optional[str] = None,
        quiet_hours: Optional[tuple] = None,
    ):
        with open(config_path) as f:
            self.config = json.load(f)

        # Connection axis
        conn_cfg = self.config["connection_axis"]
        conn_state_path = _derive_state_path(state_path, "connection_state")
        self.connection_axis = ConnectionAxis(
            state_path=conn_state_path or f"{Path(config_path).parent.parent}/workspace/companion/states/connection_state.json",
            growth_rate_per_hour=conn_cfg.get("growth_rate_per_hour", 0.08),
            threshold=conn_cfg.get("threshold", 0.50),
            contact_reset=conn_cfg.get("contact_reset", 0.40),
            drop_fraction=conn_cfg.get("drop_fraction", 0.4),
            min_value=conn_cfg.get("min_value", 0.05),
            max_value=conn_cfg.get("max_value", 1.0),
            sleep_growth_multiplier=conn_cfg.get("sleep_growth_multiplier", 0.25),
        )

        # Pride axis
        pride_cfg = self.config.get("pride_axis", {})
        pride_state_path = _derive_state_path(state_path, "pride_state")
        self.pride_axis = PrideAxis(
            state_path=pride_state_path or f"{Path(config_path).parent.parent}/workspace/companion/states/pride_state.json",
            growth_per_message=pride_cfg.get("growth_per_message", 0.30),
            decay_per_minute=pride_cfg.get("decay_per_minute", 0.98),
            sensitivity=pride_cfg.get("sensitivity", 0.20),
            base_threshold=self.connection_axis.threshold,
        )

        # Hard filter
        hf_cfg = self.config["hard_filter"]
        raw_quiet = quiet_hours or hf_cfg["quiet_hours"]
        if isinstance(raw_quiet, (list, tuple)) and len(raw_quiet) == 2 and isinstance(raw_quiet[0], int):
            quiet_hours_normalized = tuple(raw_quiet)
        else:
            quiet_hours_normalized = [
                (b[0], b[1]) for b in raw_quiet
                if isinstance(b, (list, tuple)) and len(b) == 2
            ]
        self.hard_filter = HardFilter(
            quiet_hours=quiet_hours_normalized,
            externally_accessible=hf_cfg.get("externally_accessible", True),
        )

        # HMM
        hmm_state_path = state_path or f"{Path(config_path).parent.parent}/workspace/companion/trigger_state.json"
        self.hmm = HMMStateMachine(self.config["states"], state_path=hmm_state_path)

    def compute(
        self,
        now: Optional[datetime] = None,
    ) -> TriggerDecision:
        """
        计算触发决策（两阶段：计算 + 拟人化输出）

        Args:
            now: 当前时间

        Returns:
            TriggerDecision
        """
        now = now or datetime.now()

        # === Stage 1: Numeric computation ===
        # 1. Hard filter
        passed, reason = self.hard_filter.check(now=now)
        if not passed:
            logger.debug(f"Hard filter blocked: {reason}")
            return TriggerDecision(
                should_trigger=False,
                pull="",
                hold_back=reason,
                nudge="none",
                state=self.hmm.current_state,
                connection=self.connection_axis.get_connection(),
            )

        # 2. HMM state
        state = self.hmm.transition(now=now)

        # 3. Connection axis — 积温增长（安静时段减速）
        connection = self.connection_axis.tick(now=now, quiet_hours=self._quiet_hours())

        # 5. Pride-based effective threshold
        effective_threshold = self.pride_axis.effective_threshold(now)

        # 6. Threshold comparison
        should_trigger = connection >= effective_threshold

        # 7. On trigger: reset connection + cooldown
        if should_trigger:
            self.connection_axis.on_contact(now)
            connection = self.connection_axis.get_connection()
            logger.info(
                f"[Trigger] FIRE: connection={connection:.3f} >= {effective_threshold:.3f} "
                f"(pride={self.pride_axis.get_pride(now):.3f}), state={state}"
            )

        hour = now.hour

        logger.debug(
            f"Trigger compute: connection={connection:.3f}, state={state}, "
            f"threshold={effective_threshold:.3f}(pride={self.pride_axis.get_pride(now):.3f}), "
            f"should_trigger={should_trigger}"
        )

        # === Stage 2: Anthropomorphic output ===
        pull, hold_back, nudge = self._anthropomorphize(
            connection=connection,
            state=state,
            hour=hour,
            strong=connection >= effective_threshold * 1.15,
        )

        return TriggerDecision(
            should_trigger=should_trigger,
            pull=pull,
            hold_back=hold_back,
            nudge=nudge,
            state=state,
            connection=connection,
        )

    def on_user_message(self, now: Optional[datetime] = None) -> None:
        """用户主动发消息 — 更新 pride + 重置 connection cooldown。"""
        now = now or datetime.now()
        self.pride_axis.on_user_message(now)
        self.connection_axis.on_reply(now)

    def _quiet_hours(self) -> tuple:
        """返回安静时段供 connection axis 使用（兼容单段/多段格式）。"""
        raw = self.config["hard_filter"]["quiet_hours"]
        if isinstance(raw, list) and len(raw) == 2 and isinstance(raw[0], int):
            return tuple(raw)
        return raw

    def _anthropomorphize(
        self,
        connection: float,
        state: str,
        hour: int,
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
        elif connection < 0.3:
            hold_back = "好像也没什么特别的事"
        else:
            hold_back = random.choice([
                "也许他正在忙",
                "等他有空再找我也行",
                "不用每次都主动",
            ])

        # Nudge (connection strength description)
        if connection >= 0.85:
            nudge = "很想念"
        elif connection >= 0.70:
            nudge = "有点想"
        elif connection >= 0.50:
            nudge = "偶尔想起"
        else:
            nudge = "没什么感觉"

        return pull, hold_back, nudge
