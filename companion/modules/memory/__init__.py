"""
记忆系统模块 — 温度检索 + 偏好推断 + 矛盾检测

用法：
    from companion.modules.memory import MemorySystem

    memory = MemorySystem(store_path="workspace/companion/memory_store.json")
    results = memory.search("用户喜欢什么")
    memory.record("用户喜欢吃辣", importance=0.7)
"""

from typing import List

from .fact_store import FactStore, Fact
from .preference import PreferenceInfer
from .contradiction import ContradictionDetector


class MemorySystem:
    """记忆系统统一入口"""

    def __init__(self, store_path: str = "workspace/companion/memory_store.json"):
        self.fact_store = FactStore(store_path)
        self.preference = PreferenceInfer(self.fact_store)
        self.contradiction = ContradictionDetector()

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        return self.fact_store.search(query, top_k)

    def record(self, content: str, importance: float = None) -> Fact:
        return self.fact_store.record(content, importance)

    def get_user_facts(self) -> List[dict]:
        return self.fact_store.get_user_facts()

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        return self.fact_store.get_recent_interactions(limit)

    def add_interaction(self, role: str, content: str, timestamp: str = None):
        return self.fact_store.add_interaction(role, content, timestamp)

    def infer_preferences(self) -> dict:
        return self.preference.infer()

    def check_contradictions(self, facts: List[dict]) -> List[dict]:
        return self.contradiction.detect(facts)
