"""活人感维度模块 — 8 维度量化。"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class LivenessMetrics:
    """活人感 8 维度"""
    主动性: float = 0.5      # 主动联系频率
    一致性: float = 0.5      # 性格/记忆一致性
    成长性: float = 0.5      # 关系成长弧线
    情绪化: float = 0.5      # 情绪表达丰富度
    脆弱性: float = 0.5      # 适度脆弱表达
    身体存在感: float = 0.5  # 身体感/存在感描写
    不可预测性: float = 0.5  # 非模板化回复
    依恋度: float = 0.5      # 情感依恋程度

    def to_dict(self) -> Dict[str, float]:
        return {
            "主动性": self.主动性,
            "一致性": self.一致性,
            "成长性": self.成长性,
            "情绪化": self.情绪化,
            "脆弱性": self.脆弱性,
            "身体存在感": self.身体存在感,
            "不可预测性": self.不可预测性,
            "依恋度": self.依恋度,
        }

    def overall_score(self) -> float:
        return sum(self.to_dict().values()) / 8


class LivenessTracker:
    """活人感追踪器"""

    def __init__(self):
        self.metrics = LivenessMetrics()
        self.history: List[LivenessMetrics] = []

    def update(self, **kwargs):
        """更新维度值"""
        for key, value in kwargs.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, max(0.0, min(1.0, value)))

    def snapshot(self):
        """保存当前快照"""
        self.history.append(LivenessMetrics(**self.metrics.to_dict()))

    def get_metrics(self) -> LivenessMetrics:
        return self.metrics

    def get_overall(self) -> float:
        return self.metrics.overall_score()
