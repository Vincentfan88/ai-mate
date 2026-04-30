"""L2+ 偏好推断模块 — 置信度 + 确认计数器。"""

from dataclasses import dataclass
from typing import List

from .fact_store import FactStore


@dataclass
class BeliefState:
    category: str
    content: str
    confidence: float  # 0.0 - 1.0
    confirm_count: int = 0
    deny_count: int = 0

    @property
    def trust_score(self) -> float:
        total = self.confirm_count + self.deny_count
        if total == 0:
            return self.confidence * 0.5
        ratio = self.confirm_count / total
        return ratio * min(1.0, self.confidence * (1 + total * 0.1))


class PreferenceInfer:
    """L2+ 偏好推断 — 置信度 + 确认计数器"""

    def __init__(self, fact_store: FactStore):
        self.store = fact_store
        self.beliefs: List[BeliefState] = []

    def infer(self) -> dict:
        """从事实中推断偏好"""
        facts = self.store.get_user_facts()

        categories = {
            "偏好": [],
            "习惯": [],
            "状态": [],
            "其他": [],
        }

        # Refined keyword matching with negation exclusion
        preference_keywords = ["喜欢", "爱好", "偏好", "最爱", "特别喜欢"]
        dislike_keywords = ["讨厌", "不喜欢", "不爱", "最怕", "反感"]
        habit_keywords = ["每天", "经常", "总是", "习惯", "一般", "通常"]
        state_keywords = ["累", "忙", "开心", "难过", "压力", "焦虑"]

        # Negation words to exclude
        negation_words = ["不", "没", "别", "不要", "不想", "不愿", "不能", "不会"]

        for fact in facts:
            content = fact.get("content", "")
            # Check for negation
            has_negation = any(neg in content for neg in negation_words)

            if any(kw in content for kw in preference_keywords) and not has_negation:
                categories["偏好"].append(content)
            elif any(kw in content for kw in dislike_keywords):
                categories["偏好"].append(f"（负面）{content}")
            elif any(kw in content for kw in habit_keywords):
                categories["习惯"].append(content)
            elif any(kw in content for kw in state_keywords):
                categories["状态"].append(content)
            else:
                categories["其他"].append(content)

        inferences = []
        if categories["偏好"]:
            inferences.append(f"用户偏好: {'; '.join(categories['偏好'][-3:])}")
        if categories["习惯"]:
            inferences.append(f"用户习惯: {'; '.join(categories['习惯'][-3:])}")
        if categories["状态"]:
            inferences.append(f"最近状态: {'; '.join(categories['状态'][-3:])}")

        return {
            "inferences": inferences,
            "fact_count": len(facts),
            "categories": categories,
        }
