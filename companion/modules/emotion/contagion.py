"""情绪感染：读取用户情绪，感染 AI 情绪。"""


def compute_contagion(user_emotion: str, contagion_config: dict) -> dict:
    """计算情绪感染效果"""
    contagion_map = {
        "开心": {"target": "开心", "factor": contagion_config.get("happy_infection", 0.6)},
        "难过": {"target": "担心", "factor": contagion_config.get("sad_infection", 0.4)},
        "生气": {"target": "担心", "factor": contagion_config.get("sad_infection", 0.4)},
        "焦虑": {"target": "担心", "factor": contagion_config.get("anxious_infection", 0.5)},
        "兴奋": {"target": "兴奋", "factor": contagion_config.get("happy_infection", 0.6)},
    }

    result = contagion_map.get(user_emotion, {"target": None, "factor": 0.0})
    return {
        "infected_emotion": result["target"],
        "intensity_bonus": result["factor"],
    }
