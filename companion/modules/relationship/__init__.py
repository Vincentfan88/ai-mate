"""关系阶段模块 — 6 阶段自动推进 + 持久化 + 场景乘数。"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RelationshipStage:
    """关系阶段"""
    level: int
    name: str
    name_cn: str
    expression_intensity: float
    scene_multipliers: Dict[str, float]
    progress_requirements: Optional[dict]


class RelationshipManager:
    """关系阶段管理器 — 自动推进 + 持久化"""

    def __init__(
        self,
        config_path: str = "companion/config/relationship.json",
        state_path: str = "workspace/companion/relationship_state.json",
    ):
        with open(config_path) as f:
            config = json.load(f)
        self.stages: Dict[int, RelationshipStage] = {}
        for level, data in config["stages"].items():
            self.stages[int(level)] = RelationshipStage(
                level=int(level),
                name=data["name"],
                name_cn=data["name_cn"],
                expression_intensity=data["expression_intensity"],
                scene_multipliers=data["scene_multipliers"],
                progress_requirements=data.get("progress_requirements"),
            )

        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        # Runtime state
        self.current_level = 0
        self.interaction_count = 0
        self.emotional_depth = 0.0
        self.memory_count = 0
        self.relationship_start: Optional[datetime] = None

        self._load_state()

    def _load_state(self):
        """从文件加载当前状态"""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                self.current_level = data.get("current_level", 0)
                self.interaction_count = data.get("interaction_count", 0)
                self.emotional_depth = data.get("emotional_depth", 0.0)
                self.memory_count = data.get("memory_count", 0)
                if data.get("relationship_start"):
                    self.relationship_start = datetime.fromisoformat(data["relationship_start"])
            except Exception:
                pass
        else:
            self.relationship_start = datetime.now()
            self._save_state()

    def _save_state(self):
        """保存状态到文件"""
        data = {
            "current_level": self.current_level,
            "interaction_count": self.interaction_count,
            "emotional_depth": round(self.emotional_depth, 3),
            "memory_count": self.memory_count,
            "relationship_start": self.relationship_start.isoformat() if self.relationship_start else None,
        }
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def record_interaction(self, emotional_value: float = 0.5):
        """记录一次互动"""
        self.interaction_count += 1
        # 移动平均更新情绪深度
        n = self.interaction_count
        self.emotional_depth = (self.emotional_depth * (n - 1) + emotional_value) / n
        self._save_state()

    def update_memory_count(self, count: int):
        """更新记忆数量"""
        self.memory_count = count
        self._save_state()

    def check_progress(self) -> bool:
        """检查是否可以推进关系"""
        if self.current_level >= 5:
            return False
        next_stage = self.get_stage(self.current_level + 1)
        req = next_stage.progress_requirements
        if req is None:
            return False
        return (
            self.interaction_count >= req["min_interactions"]
            and self.emotional_depth >= req["min_emotional_depth"]
            and self.memory_count >= req["min_memory_count"]
        )

    def progress(self) -> bool:
        """自动推进关系阶段"""
        if self.check_progress():
            self.current_level += 1
            self._save_state()
            return True
        return False

    def get_stage(self, level: int) -> RelationshipStage:
        """获取指定阶段"""
        return self.stages.get(level, self.stages[0])

    def get_current_stage(self) -> RelationshipStage:
        """获取当前阶段"""
        return self.get_stage(self.current_level)

    def get_scene_multiplier(self, scene_id: str) -> float:
        """获取当前阶段的场景权重倍率"""
        stage = self.get_current_stage()
        return stage.scene_multipliers.get(scene_id, 1.0)

    def get_all_stages(self) -> List[RelationshipStage]:
        return list(self.stages.values())

    def get_days_together(self, now: datetime = None) -> int:
        """获取在一起的天数"""
        now = now or datetime.now()
        if self.relationship_start:
            return (now - self.relationship_start).days
        return 0

    def get_stats(self) -> dict:
        """获取关系统计"""
        stage = self.get_current_stage()
        return {
            "level": self.current_level,
            "name": stage.name,
            "name_cn": stage.name_cn,
            "interactions": self.interaction_count,
            "emotional_depth": round(self.emotional_depth, 3),
            "memory_count": self.memory_count,
            "days_together": self.get_days_together(),
            "can_progress": self.check_progress(),
        }
