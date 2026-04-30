"""关系阶段模块 — 6 阶段关系 progression。"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RelationshipStage:
    """关系阶段"""
    level: int
    name: str
    name_cn: str
    trigger_frequency_hours: float
    expression_intensity: float
    scene_multipliers: Dict[str, float]
    progress_requirements: Optional[dict]


class RelationshipManager:
    """关系阶段管理器"""

    def __init__(self, config_path: str = "companion/config/relationship.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.stages: Dict[int, RelationshipStage] = {}
        for level, data in config["stages"].items():
            self.stages[int(level)] = RelationshipStage(
                level=int(level),
                name=data["name"],
                name_cn=data["name_cn"],
                trigger_frequency_hours=data["trigger_frequency_hours"],
                expression_intensity=data["expression_intensity"],
                scene_multipliers=data["scene_multipliers"],
                progress_requirements=data.get("progress_requirements"),
            )

    def get_stage(self, level: int) -> RelationshipStage:
        """获取指定阶段"""
        return self.stages.get(level, self.stages[0])

    def get_scene_multiplier(self, level: int, scene_id: str) -> float:
        """获取场景权重倍率"""
        stage = self.get_stage(level)
        return stage.scene_multipliers.get(scene_id, 1.0)

    def get_all_stages(self) -> List[RelationshipStage]:
        return list(self.stages.values())

    def can_progress(
        self, current_level: int, interactions: int, emotional_depth: float, memory_count: int
    ) -> bool:
        """判断是否可以进入下一阶段"""
        if current_level >= 5:
            return False  # Max level
        next_stage = self.get_stage(current_level + 1)
        req = next_stage.progress_requirements
        if req is None:
            return True
        return (
            interactions >= req["min_interactions"]
            and emotional_depth >= req["min_emotional_depth"]
            and memory_count >= req["min_memory_count"]
        )
