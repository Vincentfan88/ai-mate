"""Agent integration layer — wires companion modules into Mini-Agent."""

from .persona import build_system_prompt, load_persona
from .tools import (
    CompanionEmotionTool,
    CompanionFeishuTool,
    CompanionMBTITool,
    CompanionMemoryTool,
    CompanionSceneTool,
    CompanionStateTool,
    CompanionTimeTool,
    CompanionTrendingTool,
    CompanionTriggerTool,
    CompanionFlashbackTool,
)

__all__ = [
    "CompanionStateTool",
    "CompanionMemoryTool",
    "CompanionEmotionTool",
    "CompanionTriggerTool",
    "CompanionMBTITool",
    "CompanionFeishuTool",
    "CompanionSceneTool",
    "CompanionTrendingTool",
    "CompanionTimeTool",
    "CompanionFlashbackTool",
    "load_persona",
    "build_system_prompt",
]
