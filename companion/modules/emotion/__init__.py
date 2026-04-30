"""
情绪系统模块 — 8 种情绪 + 强度二维模型

用法：
    from companion.modules.emotion import EmotionSystem

    emotion = EmotionSystem()
    result = emotion.get_current_emotion("user_message")
    emotion.save_residue()
"""

from .core import EmotionSystem
from .circadian import compute_circadian
