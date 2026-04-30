"""
MBTI 模块 — 16 类型全维度 + 5 适配器

用法：
    from companion.modules.mbti import MBTIAdapter
    adapter = MBTIAdapter()
    profile = adapter.get_profile("ENFP")
"""

from .mbti_type import MBTIType, get_type, ALL_TYPES
from .adapters import (
    MBTIAdapter,
    MBTIProfile,
    SpeechConfig,
    EmotionalConfig,
    BehaviorConfig,
    LivenessConfig,
    SceneWeightConfig,
)
