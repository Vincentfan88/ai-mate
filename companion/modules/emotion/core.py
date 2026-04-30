"""8 种情绪 + 强度二维模型核心模块。"""

import json
import random
from datetime import datetime
from typing import List, Optional

from .circadian import compute_circadian
from .event_impact import get_event_bonus
from .contagion import compute_contagion
from .residue import EmotionResidue


class EmotionSystem:
    """8 种情绪 + 强度二维模型"""

    def __init__(
        self,
        config_path: str = "companion/config/emotions.json",
        state_file: str = "workspace/companion/emotion_state.json",
    ):
        with open(config_path) as f:
            self.config = json.load(f)
        self.emotion_types = self.config["emotion_types"]
        self.residue = EmotionResidue(state_file, self.config["residue"]["decay_factor"])

    def get_current_emotion(
        self, event_type: str, user_emotion: str = None
    ) -> dict:
        now = datetime.now()
        hour = now.hour

        # 1. Circadian base
        circadian_cfg = self.config["circadian"]
        circadian = compute_circadian(
            hour=hour,
            peak_hour=circadian_cfg["peak_hour"],
            trough_hour=circadian_cfg["trough_hour"],
            amplitude=circadian_cfg["base_amplitude"],
            baseline=circadian_cfg["baseline"],
        )

        # 2. Event bonus
        event_bonus = get_event_bonus(event_type, self.config["event_weights"])

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

        # 6. Select dominant emotion
        dominant = self._select_emotion(infected_emotion, intensity)

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
        self, infected_emotion: Optional[str], intensity: float
    ) -> str:
        """选择主导情绪"""
        # If contagion activated, use infected emotion
        if infected_emotion and infected_emotion in self.emotion_types:
            return infected_emotion

        # Weighted random selection based on intensity
        # Higher intensity → more likely to select strong emotions
        if intensity > 0.7:
            # Strong emotions
            pool = ["开心", "兴奋", "想念"]
        elif intensity > 0.5:
            # Moderate emotions
            pool = ["开心", "想念", "撒娇", "害羞"]
        else:
            # Calm emotions
            pool = ["平静", "想念", "害羞"]

        # Filter to only valid emotion types
        valid_pool = [e for e in pool if e in self.emotion_types]
        if not valid_pool:
            valid_pool = ["开心", "想念"]

        return random.choice(valid_pool)
