"""Companion 模块注册表 — 统一管理所有模块实例。"""

from typing import Dict, Optional

from companion.modules.memory import MemorySystem
from companion.modules.emotion import EmotionSystem
from companion.modules.trigger import TriggerEngine
from companion.modules.mbti import MBTIAdapter
from companion.modules.scene import SceneLibrary
from companion.modules.relationship import RelationshipManager
from companion.modules.liveness import LivenessTracker
from companion.modules.extras import AnniversaryTracker, HabitTracker, TrendingCache


class CompanionRegistry:
    """Companion 模块注册表"""

    def __init__(
        self,
        workspace: str = "workspace/companion",
        config_dir: str = "companion/config",
        mbti_type: str = "ENFP",
        relationship_level: int = 0,
    ):
        self.workspace = workspace
        self.config_dir = config_dir
        self.mbti_type = mbti_type
        self.relationship_level = relationship_level

        # Lazy-initialized modules
        self._modules: Dict[str, object] = {}

    @property
    def memory(self) -> MemorySystem:
        return self._get_or_create("memory", lambda: MemorySystem(
            store_path=f"{self.workspace}/memory_store.json"
        ))

    @property
    def emotion(self) -> EmotionSystem:
        return self._get_or_create("emotion", lambda: EmotionSystem(
            config_path=f"{self.config_dir}/emotions.json",
            state_file=f"{self.workspace}/emotion_state.json",
        ))

    @property
    def trigger(self) -> TriggerEngine:
        return self._get_or_create("trigger", lambda: TriggerEngine(
            config_path=f"{self.config_dir}/triggers.json",
        ))

    @property
    def mbti(self) -> MBTIAdapter:
        return self._get_or_create("mbti", lambda: MBTIAdapter())

    @property
    def scenes(self) -> SceneLibrary:
        return self._get_or_create("scenes", lambda: SceneLibrary(
            config_path=f"{self.config_dir}/scenes.json",
        ))

    @property
    def relationship(self) -> RelationshipManager:
        return self._get_or_create("relationship", lambda: RelationshipManager(
            config_path=f"{self.config_dir}/relationship.json",
        ))

    @property
    def liveness(self) -> LivenessTracker:
        return self._get_or_create("liveness", lambda: LivenessTracker())

    @property
    def anniversary(self) -> AnniversaryTracker:
        return self._get_or_create("anniversary", lambda: AnniversaryTracker())

    @property
    def habits(self) -> HabitTracker:
        return self._get_or_create("habits", lambda: HabitTracker(
            config_path=f"{self.config_dir}/habits.json",
        ))

    @property
    def trending(self) -> TrendingCache:
        return self._get_or_create("trending", lambda: TrendingCache(
            cache_path=f"{self.workspace}/trending_cache.json",
        ))

    def _get_or_create(self, name: str, factory):
        if name not in self._modules:
            self._modules[name] = factory()
        return self._modules[name]

    def get_module(self, name: str) -> Optional[object]:
        return self._modules.get(name)
