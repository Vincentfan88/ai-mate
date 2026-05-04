"""情绪残留：跨 session 的情绪连续性，随时间衰减。"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class EmotionResidue:
    """情绪残留：跨 session 的情绪连续性，带时间衰减"""

    def __init__(self, state_file: str = "workspace/companion/states/emotion_state.json", decay: float = 0.3):
        self.state_file = Path(state_file)
        self.decay = decay  # 每小时衰减系数（指数衰减底数）
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(f"[EmotionResidue] 状态文件 JSON 解析失败: {e}")
            return {}
        except OSError as e:
            logger.warning(f"[EmotionResidue] 状态文件读取失败: {e}")
            return {}

    def save(self, emotion: str, intensity: float):
        self.state_file.write_text(json.dumps({
            "emotion": emotion,
            "intensity": intensity,
            "residue_bonus": round(intensity * self.decay, 3),
            "saved_at": time.time(),
        }, ensure_ascii=False))

    def get_residue_bonus(self) -> dict:
        state = self.load()
        if not state or "saved_at" not in state:
            return {"emotion": state.get("emotion"), "bonus": 0.0}

        elapsed_hours = (time.time() - state["saved_at"]) / 3600
        # 指数衰减：bonus(t) = initial * decay^t，每小时衰减一次
        decayed = state.get("residue_bonus", 0.0) * (self.decay ** elapsed_hours)
        return {
            "emotion": state.get("emotion"),
            "bonus": round(decayed, 3),
        }
