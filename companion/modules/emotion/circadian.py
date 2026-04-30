"""昼夜节律：余弦波模拟，峰值 21:00，谷值 09:00。"""

import math
from datetime import datetime


def compute_circadian(
    hour: int = None,
    peak_hour: int = 21,
    trough_hour: int = 9,
    amplitude: float = 0.4,
    baseline: float = 0.3,
) -> float:
    """计算指定小时的昼夜节律情绪基线"""
    if hour is None:
        hour = datetime.now().hour

    phase = (hour - trough_hour) / 24 * 2 * math.pi
    value = baseline + amplitude * math.cos(phase - math.pi)
    return max(0.0, min(1.0, value))
