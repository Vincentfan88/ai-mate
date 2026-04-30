"""事件影响加成模块。"""


def get_event_bonus(event_type: str, event_weights: dict) -> float:
    """获取事件影响加成"""
    return event_weights.get(event_type, 0.0)
