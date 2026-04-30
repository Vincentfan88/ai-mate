"""Weibull 分布采样模块 — 用于不规则联系间隔模拟。"""

import math
import random


def weibull_sample(alpha: float = 1.5, beta: float = 12.0) -> float:
    """
    Weibull 采样：interval = beta * (-ln(U))^(1/alpha)

    Args:
        alpha: 形状参数（影响分布形态）
        beta: 尺度参数（平均间隔时间，小时）

    Returns:
        采样的间隔时间（小时）
    """
    u = random.random()
    return beta * (-math.log(u)) ** (1 / alpha)


def compute_hour_bonus(hour: int, hour_bonus: dict) -> float:
    """计算小时加成"""
    if 6 <= hour < 11:
        return hour_bonus.get("morning", 0.15)
    elif 11 <= hour < 17:
        return hour_bonus.get("noon", 0.25)
    elif 17 <= hour < 23:
        return hour_bonus.get("evening", 0.45)
    else:
        return hour_bonus.get("night", 0.30)
