"""矛盾检测模块 — 两阶段：关键词匹配 → 语义判断。"""

from typing import List, Optional


class ContradictionDetector:
    """矛盾检测 — 两阶段：关键词匹配 → 语义判断"""

    def __init__(self):
        self.contradiction_pairs = [
            ("喜欢", "讨厌"),
            ("爱", "不爱"),
            ("经常", "很少"),
            ("总是", "从不"),
            ("想要", "不想"),
            ("觉得好", "觉得不好"),
        ]

    def detect(self, facts: List[dict]) -> List[dict]:
        """检测事实之间的矛盾"""
        contradictions = []

        for i, f1 in enumerate(facts):
            for f2 in facts[i + 1:]:
                pair = self._check_contradiction(f1, f2)
                if pair:
                    contradictions.append(pair)

        return contradictions

    def _check_contradiction(self, f1: dict, f2: dict) -> Optional[dict]:
        """检查两条事实是否矛盾"""
        c1 = f1.get("content", "")
        c2 = f2.get("content", "")

        for kw1, kw2 in self.contradiction_pairs:
            if kw1 in c1 and kw2 in c2:
                return {
                    "fact1": f1,
                    "fact2": f2,
                    "conflict_keywords": (kw1, kw2),
                    "severity": "medium",
                }
            if kw2 in c1 and kw1 in c2:
                return {
                    "fact1": f1,
                    "fact2": f2,
                    "conflict_keywords": (kw2, kw1),
                    "severity": "medium",
                }

        return None

    def should_follow_up(self, contradictions: List[dict]) -> bool:
        """判断是否需要追问"""
        return len(contradictions) > 0
