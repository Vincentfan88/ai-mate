"""情绪残留：跨 session 的情绪连续性。"""

import json
from pathlib import Path


class EmotionResidue:
    """情绪残留：跨 session 的情绪连续性"""

    def __init__(self, state_file: str = "workspace/companion/emotion_state.json", decay: float = 0.3):
        self.state_file = Path(state_file)
        self.decay = decay
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return {}

    def save(self, emotion: str, intensity: float):
        self.state_file.write_text(json.dumps({
            "emotion": emotion,
            "intensity": intensity,
            "residue_bonus": round(intensity * self.decay, 3),
        }, ensure_ascii=False))

    def get_residue_bonus(self) -> dict:
        state = self.load()
        return {
            "emotion": state.get("emotion"),
            "bonus": state.get("residue_bonus", 0.0),
        }
