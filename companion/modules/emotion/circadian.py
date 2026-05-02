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
    """计算指定小时的昼夜节律情绪基线

    公式: value = baseline + amplitude * cos((hour - trough) / 24 * 2π - π)
    确保谷值 ≥ 0：振幅不应超过基线（amplitude <= baseline）。
    若配置值导致谷值 < 0，自动归一化到 [0,1]。
    """
    if hour is None:
        hour = datetime.now().hour

    phase = (hour - trough_hour) / 24 * 2 * math.pi
    raw = baseline + amplitude * math.cos(phase - math.pi)

    # 归一化到 [0,1]（防止 amplitude > baseline 时谷值被 clamp）
    min_val = baseline - amplitude
    max_val = baseline + amplitude
    if max_val != min_val:
        normalized = (raw - min_val) / (max_val - min_val)
    else:
        normalized = 0.5
    return max(0.0, min(1.0, normalized))
