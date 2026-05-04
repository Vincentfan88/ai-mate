"""8 种情绪 + 强度二维模型核心模块。"""

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .circadian import compute_circadian
from .event_impact import get_event_bonus
from .contagion import compute_contagion
from .residue import EmotionResidue

logger = logging.getLogger(__name__)


def _now_bj() -> datetime:
    """获取北京时间 (UTC+8) 的 naive datetime。"""
    utc_now = datetime.now(timezone.utc)
    return (utc_now.replace(tzinfo=None) + timedelta(hours=8))

# 情绪之间的"距离"矩阵 — 相近情绪过渡平滑，远距离情绪变化突兀
_EMOTION_DISTANCE: Dict[str, Dict[str, float]] = {
    "开心": {"兴奋": 0.3, "想念": 0.5, "撒娇": 0.4, "害羞": 0.5, "难过": 0.8, "生气": 0.9, "担心": 0.7},
    "兴奋": {"开心": 0.3, "想念": 0.6, "撒娇": 0.5, "害羞": 0.6, "难过": 0.9, "生气": 0.8, "担心": 0.7},
    "想念": {"开心": 0.5, "兴奋": 0.6, "撒娇": 0.4, "害羞": 0.3, "难过": 0.5, "生气": 0.7, "担心": 0.4},
    "撒娇": {"开心": 0.4, "兴奋": 0.5, "想念": 0.4, "害羞": 0.3, "难过": 0.6, "生气": 0.8, "担心": 0.5},
    "害羞": {"开心": 0.5, "兴奋": 0.6, "想念": 0.3, "撒娇": 0.3, "难过": 0.5, "生气": 0.7, "担心": 0.4},
    "难过": {"开心": 0.8, "兴奋": 0.9, "想念": 0.5, "撒娇": 0.6, "害羞": 0.5, "生气": 0.4, "担心": 0.3},
    "生气": {"开心": 0.9, "兴奋": 0.8, "想念": 0.7, "撒娇": 0.8, "害羞": 0.7, "难过": 0.4, "担心": 0.4},
    "担心": {"开心": 0.7, "兴奋": 0.7, "想念": 0.4, "撒娇": 0.5, "害羞": 0.4, "难过": 0.3, "生气": 0.4},
}


class EmotionSystem:
    """8 种情绪 + 强度二维模型"""

    def __init__(
        self,
        config_path: str = "companion/config/emotions.json",
        state_file: str = "workspace/companion/states/emotion_state.json",
        emotional_config: Optional[dict] = None,
    ):
        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)
        self.emotion_types = self.config["emotion_types"]
        self.residue = EmotionResidue(state_file, self.config["residue"]["decay_factor"])

        # Session-level cache for consistency
        self._last_emotion: Optional[str] = None
        self._last_intensity: float = 0.0
        self._session_event_key: Optional[str] = None

        # MBTI 情绪偏好（来自 MBTI emotional_config）
        self.emotional_config = emotional_config or {}

    # 用户情绪 → 事件类型映射，使 event_weight 配置生效
    _EMOTION_EVENT_MAP: Dict[str, str] = {
        "开心": "user_happy",
        "难过": "user_sad",
        "生气": "user_angry",
        "焦虑": "user_anxious",
        "兴奋": "user_happy",
        "担心": "user_anxious",
    }

    def get_current_emotion(
        self, event_type: str, user_emotion: str = None
    ) -> dict:
        now = _now_bj()
        hour = now.hour

        # 1. 自动映射：user_emotion → 对应的 event_type（使 event_weight 配置生效）
        effective_event = event_type
        if user_emotion and user_emotion in self._EMOTION_EVENT_MAP:
            effective_event = self._EMOTION_EVENT_MAP[user_emotion]

        # 2. Circadian base
        circadian_cfg = self.config["circadian"]
        circadian = compute_circadian(
            hour=hour,
            peak_hour=circadian_cfg["peak_hour"],
            trough_hour=circadian_cfg["trough_hour"],
            amplitude=circadian_cfg["base_amplitude"],
            baseline=circadian_cfg["baseline"],
        )

        # 3. Event bonus
        event_bonus = get_event_bonus(effective_event, self.config["event_weights"])

        # 3. Contagion
        contagion_bonus = 0.0
        infected_emotion = None
        if user_emotion:
            contagion_result = compute_contagion(user_emotion, self.config["contagion"])
            if contagion_result["infected_emotion"]:
                contagion_bonus = contagion_result["intensity_bonus"]
                infected_emotion = contagion_result["infected_emotion"]

        # 4. Residue
        residue = self.residue.get_residue_bonus()
        residue_bonus = residue.get("bonus", 0.0)

        # 5. Compute intensity
        intensity = circadian + event_bonus + contagion_bonus + residue_bonus
        intensity = max(0.0, min(1.0, intensity))

        # 6. Select dominant emotion (MBTI-aware + session-cached + smooth transition)
        session_key = f"{infected_emotion}_{user_emotion}_{intensity:.1f}"
        if self._session_event_key == session_key and self._last_emotion:
            dominant = self._last_emotion
        else:
            dominant = self._select_emotion(
                infected_emotion, intensity, self._last_emotion, self._last_intensity
            )
            self._session_event_key = session_key

        # 7. Store residue for next session
        self._last_emotion = dominant
        self._last_intensity = intensity

        return {
            "emotion": dominant,
            "intensity": round(intensity, 3),
            "circadian_base": round(circadian, 3),
            "event_bonus": event_bonus,
            "contagion_bonus": round(contagion_bonus, 3),
            "residue_bonus": round(residue_bonus, 3),
            "infected_emotion": infected_emotion,
            "tone_description": self.get_tone_description(dominant),
        }

    def get_tone_description(self, emotion: str) -> str:
        """获取情绪对应的语气描述"""
        return self.config["tone_mapping"].get(emotion, "平静自然")

    def save_residue(self):
        """保存当前情绪残留"""
        if hasattr(self, "_last_emotion"):
            self.residue.save(self._last_emotion, self._last_intensity)

    def _select_emotion(
        self,
        infected_emotion: Optional[str],
        intensity: float,
        prev_emotion: Optional[str] = None,
        prev_intensity: float = 0.0,
    ) -> str:
        """选择主导情绪 — MBTI 感知 + 平滑过渡"""
        # If contagion activated, use infected emotion
        if infected_emotion and infected_emotion in self.emotion_types:
            return infected_emotion

        # Base pool from intensity
        if intensity > 0.7:
            pool = ["开心", "兴奋", "想念"]
        elif intensity > 0.5:
            pool = ["开心", "想念", "撒娇", "害羞"]
        else:
            pool = ["开心", "想念", "害羞"]

        # Filter to valid emotion types
        valid_pool = [e for e in pool if e in self.emotion_types]
        if not valid_pool:
            valid_pool = ["开心", "想念"]

        # MBTI 情绪偏好加权
        weights = self._mbti_emotion_weights(valid_pool)

        # 平滑过渡：给前一次情绪增加惯性权重（避免跳跃）
        if prev_emotion and prev_emotion in valid_pool:
            for i, em in enumerate(valid_pool):
                if em == prev_emotion:
                    dist = 0.0  # 完全相同，最大惯性
                else:
                    dist = _EMOTION_DISTANCE.get(prev_emotion, {}).get(em, 0.5)
                inertia = max(0.1, 1.0 - dist)
                weights[i] += inertia * 0.5  # 惯性系数 50%

        # Normalize weights
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        return random.choices(valid_pool, weights=weights, k=1)[0]

    def _mbti_emotion_weights(self, pool: List[str]) -> List[float]:
        """根据 MBTI 情绪配置生成偏好权重"""
        if not self.emotional_config:
            return [1.0] * len(pool)

        primary = self.emotional_config.get("primary_emotions", [])
        triggers = self.emotional_config.get("emotion_triggers", {})
        disclosure = self.emotional_config.get("self_disclosure_tendency", 0.5)

        weights = []
        for em in pool:
            w = 1.0
            # 主要情绪偏好加分
            if em in primary:
                w += 0.5
            # 自我揭露倾向影响想念类情绪
            if em in ("想念", "撒娇") and disclosure > 0.6:
                w += 0.2
            weights.append(w)
        return weights
