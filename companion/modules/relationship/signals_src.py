"""
关系信号系统 - Relationship Signal Processing

从对话中提取亲密度信号，更新 UserProfile intimacy/trust，
管理阶段演进，在沉默时触发衰减。
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:
    from core.stores.profile import UserProfile
    from core.shared_state import SharedState

logger = logging.getLogger("relationship")

# ===== 信号阈值常量 =====
LONG_RESPONSE_MIN_CHARS = 30
INITIATED_TOPIC_MIN_CHARS = 5
SHORT_RESPONSE_MAX_CHARS = 5
RELATIONSHIP_SAMPLE_RATE = 0.30  # 30% 采样率

# ===== 信号定义 =====
# 格式: "信号名": (关键词列表, intimacy_delta, trust_delta)

POSITIVE_SIGNALS = {
    "love_expression":     (["爱你", "喜欢", "爱"],              0.015, 0.005),
    "missing_expression":   (["想你", "想念", "想你了"],         0.010, 0.003),
    "physical_affection":   (["抱抱", "亲亲", "抱", "亲", "贴贴"], 0.020, 0.005),
    "praise":              (["可爱", "漂亮", "厉害", "棒", "乖"], 0.005, 0.002),
    "shared_vulnerability":(["难过", "伤心", "害怕", "担心"],    0.005, 0.010),
    "deep_topic":           (["未来", "以后", "我们", "一起", "规划"], 0.008, 0.005),
    "playful_flirt":        (["调戏", "撩", "调皮", "哼", "吃醋"], 0.005, 0.002),
    "personal_sharing":     (["我告诉你", "跟你说", "秘密", "其实"], 0.003, 0.008),
    "long_response":        (">30字",  0.002, 0.001),
    "initiated_topic":      (">5字用户开头", 0.001, 0.001),
}

NEGATIVE_SIGNALS = {
    "cold_response":  (["哦", "嗯", "好吧", "随便"],         -0.005, -0.002),
    "rejection":      (["不要", "不用", "算了", "没空"],     -0.015, -0.005),
    "dismissal":      (["知道了", "行吧", "就这样", "哦"],   -0.003, -0.002),
    "short_response": ("<5字", -0.003, -0.001),
}

# 阶段演进最低要求
STAGE_REQUIREMENTS = {
    "stranger":     {"min_days": 7,  "min_interactions": 10, "required_signals": {"love_expression": 1, "personal_sharing": 1}},
    "acquaintance": {"min_days": 14, "min_interactions": 25, "required_signals": {"missing_expression": 1, "playful_flirt": 1}},
    "close":        {"min_days": 30, "min_interactions": 50, "required_signals": {"physical_affection": 1, "deep_topic": 1}},
    "dating":       {"min_days": 60, "min_interactions": 100, "required_signals": {"love_expression": 2, "shared_vulnerability": 1}},
    # deep_love: 无上限，持续自然积累
}


def evaluate_signals(user_msg: str, agent_msg: str) -> Dict:
    """评估一轮对话中的亲密度信号。Returns: {intimacy_delta, trust_delta, matched_signals}"""

    combined = user_msg + " " + agent_msg
    intimacy_delta = 0.0
    trust_delta = 0.0
    matched: List[str] = []

    for name, (keywords, i_delta, t_delta) in POSITIVE_SIGNALS.items():
        if name == "long_response":
            if len(user_msg) > LONG_RESPONSE_MIN_CHARS:
                intimacy_delta += i_delta
                trust_delta += t_delta
                matched.append(name)
        elif name == "initiated_topic":
            if len(user_msg) > INITIATED_TOPIC_MIN_CHARS:
                intimacy_delta += i_delta
                trust_delta += t_delta
                matched.append(name)
        elif any(kw in combined for kw in keywords):
            intimacy_delta += i_delta
            trust_delta += t_delta
            matched.append(name)

    for name, (keywords, i_delta, t_delta) in NEGATIVE_SIGNALS.items():
        if name == "short_response":
            if len(user_msg) < SHORT_RESPONSE_MAX_CHARS:
                intimacy_delta += i_delta
                trust_delta += t_delta
                matched.append("!" + name)
        elif any(kw in user_msg for kw in keywords):
            intimacy_delta += i_delta
            trust_delta += t_delta
            matched.append("!" + name)

    return {"intimacy_delta": intimacy_delta, "trust_delta": trust_delta, "matched_signals": matched}


def check_stage_progression(user_profile) -> Tuple[bool, str]:
    """检查关系是否能进入下一阶段。Returns: (can_progress, next_stage)"""
    current_stage = user_profile.get_stage_name()
    stage_order = ["stranger", "acquaintance", "close", "dating", "deep_love"]

    if current_stage not in stage_order:
        return False, current_stage
    idx = stage_order.index(current_stage)
    if idx >= len(stage_order) - 1:
        return False, current_stage

    next_stage = stage_order[idx + 1]
    reqs = STAGE_REQUIREMENTS.get(current_stage, {})
    if not reqs:
        return False, current_stage

    duration = user_profile.get_relationship_duration()
    if duration["days"] < reqs["min_days"]:
        return False, next_stage

    total_interactions = sum(user_profile.learned_topics.values())
    if total_interactions < reqs["min_interactions"]:
        return False, next_stage

    for sig_name, min_count in reqs.get("required_signals", {}).items():
        if user_profile.learned_topics.get(sig_name, 0) < min_count:
            return False, next_stage

    return True, next_stage


def apply_silence_decay(user_profile: "UserProfile", days_silent: int) -> None:
    """按沉默天数衰减 intimacy/trust。每天 -0.01，下限为当前阶段最低值。"""
    if days_silent <= 0:
        return
    stage = user_profile.get_stage_name()
    stage_min = {
        "stranger": 0.0, "acquaintance": 0.2,
        "close": 0.4, "dating": 0.6, "deep_love": 0.8
    }.get(stage, 0.0)
    decay = days_silent * 0.01
    user_profile.intimacy_level = max(stage_min, user_profile.intimacy_level - decay)
    user_profile.trust_level = max(0.0, user_profile.trust_level - decay * 0.5)
    user_profile._save_data()
    logger.info(f"[关系衰减] 沉默{days_silent}天，intimacy={user_profile.intimacy_level:.3f}")


def process_relationship_update(state: "SharedState", user_msg: str, agent_msg: str) -> None:
    """每轮对话后调用（30%采样率），评估信号并更新 UserProfile。"""
    if random.random() > RELATIONSHIP_SAMPLE_RATE:
        return

    signals = evaluate_signals(user_msg, agent_msg)
    if not signals["matched_signals"]:
        return

    profile = state.user_profile

    # 记录命中的正面信号到 learned_topics（用于阶段演进检查）
    for sig in signals["matched_signals"]:
        if sig.startswith("!"):
            continue
        profile.learn_topic(sig)

    if signals["intimacy_delta"] != 0:
        profile.update_intimacy(signals["intimacy_delta"])
    if signals["trust_delta"] != 0:
        profile.update_trust(signals["trust_delta"])

    can_progress, next_stage = check_stage_progression(profile)
    if can_progress:
        _do_stage_transition(state, next_stage)

    _sync_to_memory(state, profile)

    logger.info(
        f"[关系信号] {signals['matched_signals']} → "
        f"intimacy={profile.intimacy_level:.3f} stage={profile.get_stage_name()}"
    )


def _do_stage_transition(state, new_stage: str) -> None:
    """执行阶段转换"""
    old_stage = state.user_profile.get_stage_name()
    target_intimacy = {
        "stranger": 0.2, "acquaintance": 0.4,
        "close": 0.6, "dating": 0.8, "deep_love": 0.95
    }.get(new_stage, 0.5)
    state.user_profile.intimacy_level = target_intimacy
    state.user_profile._log_growth("stage_advanced", {"from": old_stage, "to": new_stage})
    state.user_profile._save_data()
    logger.info(f"[关系进阶] {old_stage} → {new_stage}")


def _sync_to_memory(state, profile) -> None:
    """将阶段信息写入 HybridMemorySystem structured 层（使用原始阶段名）"""
    if state.memory is None:
        return
    if not hasattr(state.memory, '_struct_store') or not hasattr(state.memory, 'save_structured'):
        return
    structured_stage = profile.get_stage_name()
    if state.memory.structured.get("relationship_stage") != structured_stage:
        state.memory.structured["relationship_stage"] = structured_stage
        try:
            state.memory.save_structured()
        except Exception as e:
            logger.warning(f"[关系信号] 阶段持久化失败: {e}")