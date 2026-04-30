"""场景模块 — 从 JSON 加载场景配置。"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Scene:
    """场景定义"""
    id: str
    name: str
    base_weight: float
    suitable_moods: List[str]
    suitable_hours: List[int]
    prompt_hint: str
    example: str

    def is_suitable_for_hour(self, hour: int) -> bool:
        return hour in self.suitable_hours

    def is_suitable_for_mood(self, mood: str) -> bool:
        return mood in self.suitable_moods


class SceneLibrary:
    """场景库"""

    def __init__(self, config_path: str = "companion/config/scenes.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.scenes: Dict[str, Scene] = {}
        for scene_id, data in config["scenes"].items():
            self.scenes[scene_id] = Scene(
                id=scene_id,
                name=data["name"],
                base_weight=data["base_weight"],
                suitable_moods=data.get("suitable_moods", []),
                suitable_hours=data.get("suitable_hours", []),
                prompt_hint=data.get("prompt_hint", ""),
                example=data.get("example", ""),
            )

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return self.scenes.get(scene_id)

    def get_suitable_scenes(self, hour: int, mood: str) -> List[Scene]:
        """获取当前时间和心情下合适的场景"""
        suitable = []
        for scene in self.scenes.values():
            if scene.is_suitable_for_hour(hour) and scene.is_suitable_for_mood(mood):
                suitable.append(scene)
        suitable.sort(key=lambda s: s.base_weight, reverse=True)
        return suitable

    def get_all_scenes(self) -> List[Scene]:
        return list(self.scenes.values())
