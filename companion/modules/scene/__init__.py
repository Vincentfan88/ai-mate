"""场景模块 — 加权匹配（基础权重 × 心境 × 时段 × 关系阶段系数）。"""

import json
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


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
        if not self.suitable_hours:
            return True
        return hour in self.suitable_hours

    def is_suitable_for_mood(self, mood: str) -> bool:
        if not self.suitable_moods:
            return True
        return mood in self.suitable_moods


class SceneLibrary:
    """场景库 — 加权匹配算法"""

    def __init__(self, config_path: str = "companion/config/scenes.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.scenes: Dict[str, Scene] = {}
        scenes_data = config.get("scenes")
        if not scenes_data:
            raise ValueError(f"场景配置为空或缺失 'scenes' 字段: {config_path}")
        for scene_id, data in scenes_data.items():
            if "name" not in data:
                raise ValueError(f"场景 '{scene_id}' 缺少必填字段 'name'")
            self.scenes[scene_id] = Scene(
                id=scene_id,
                name=data["name"],
                base_weight=data.get("base_weight", 1.0),
                suitable_moods=data.get("suitable_moods", []),
                suitable_hours=data.get("suitable_hours", []),
                prompt_hint=data.get("prompt_hint", ""),
                example=data.get("example", ""),
            )

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return self.scenes.get(scene_id)

    def get_suitable_scenes(
        self,
        hour: int,
        mood: str,
        relationship_multiplier_fn=None,  # Callable[[str], float]
        top_k: int = 5,
    ) -> List[Tuple[Scene, float]]:
        """获取加权排序后的场景列表

        Returns:
            [(scene, weighted_score), ...]
        """
        scored = []
        for scene in self.scenes.values():
            # 1. 硬过滤
            if not scene.is_suitable_for_hour(hour):
                continue
            if not scene.is_suitable_for_mood(mood):
                continue

            # 2. 加权计算
            score = scene.base_weight

            # 3. 关系阶段乘数
            if relationship_multiplier_fn:
                score *= relationship_multiplier_fn(scene.id)

            scored.append((scene, round(score, 3)))

        # 按权重排序
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def pick_scene(
        self,
        hour: int,
        mood: str,
        relationship_multiplier_fn=None,
    ) -> Optional[Tuple[Scene, float]]:
        """按权重随机选择一个场景（加权采样）"""
        scored = self.get_suitable_scenes(hour, mood, relationship_multiplier_fn)
        if not scored:
            return None

        scenes, weights = zip(*scored)
        # 归一化权重
        total = sum(weights)
        if total <= 0:
            return scored[0]

        probs = [w / total for w in weights]
        idx = random.choices(range(len(scenes)), weights=probs, k=1)[0]
        return scored[idx]

    def get_all_scenes(self) -> List[Scene]:
        return list(self.scenes.values())
