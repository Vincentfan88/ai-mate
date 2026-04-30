"""Tool 适配器层 — 将 companion 模块包装为 Mini-Agent Tools。"""

from typing import Optional

from companion.modules.registry import CompanionRegistry


class BaseCompanionTool:
    """Tool 基类 — 所有 companion Tool 的公共基类"""

    name: str = "base_tool"
    description: str = "Base companion tool"

    def __init__(self, registry: Optional[CompanionRegistry] = None):
        self.registry = registry

    def set_registry(self, registry: CompanionRegistry):
        self.registry = registry


class StateTool(BaseCompanionTool):
    """状态查询 Tool — 获取当前情绪/时间/关系阶段"""

    name = "companion_state"
    description = "Get current companion state (emotion, time context, relationship stage)"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        from companion.modules.extras import TimeContext
        emotion = registry.emotion.get_current_emotion("time_passage")
        ctx = TimeContext.from_now()
        stage = registry.relationship.get_stage(registry.relationship_level)

        return (
            f"当前情绪: {emotion['emotion']} (强度: {emotion['intensity']})\n"
            f"时间: {ctx.time_description}\n"
            f"关系阶段: {stage.name_cn} ({stage.name})"
        )


class MemoryTool(BaseCompanionTool):
    """记忆操作 Tool — 记录/搜索/推断偏好"""

    name = "companion_memory"
    description = "Record or search companion memories"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        action = args.get("action", "search")
        if action == "record":
            content = args.get("content", "")
            if not content:
                return "Error: content is required"
            registry.memory.record(content)
            return f"已记录: {content}"
        elif action == "search":
            query = args.get("query", "")
            results = registry.memory.search(query)
            if not results:
                return f"未找到关于 '{query}' 的记忆"
            lines = [f"- {r['content']} (温度: {r.get('temperature', 0):.2f})" for r in results[:5]]
            return f"找到 {len(results)} 条记忆:\n" + "\n".join(lines)
        elif action == "preferences":
            prefs = registry.memory.infer_preferences()
            inferences = prefs.get("inferences", [])
            if not inferences:
                return "还没有足够的信息推断偏好"
            return "\n".join(inferences)
        else:
            return f"Unknown action: {action}"


class EmotionTool(BaseCompanionTool):
    """情绪查询 Tool — 获取当前情绪状态"""

    name = "companion_emotion"
    description = "Get or update companion emotion state"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        event_type = args.get("event_type", "time_passage")
        user_emotion = args.get("user_emotion")

        emotion = registry.emotion.get_current_emotion(event_type, user_emotion)
        registry.emotion.save_residue()

        return (
            f"当前情绪: {emotion['emotion']}\n"
            f"强度: {emotion['intensity']}\n"
            f"语气: {emotion['tone_description']}"
        )


class TriggerTool(BaseCompanionTool):
    """触发决策 Tool — 两阶段拟人化输出"""

    name = "companion_trigger"
    description = "Decide whether to proactively contact user"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        hours_since = args.get("hours_since_last_contact", 12)
        decision = registry.trigger.compute(hours_since_last_contact=hours_since)

        return (
            f"是否联系: {'是' if decision.should_trigger else '否'}\n"
            f"想联系的理由: {decision.pull}\n"
            f"忍住的理由: {decision.hold_back}\n"
            f"冲动: {decision.nudge}\n"
            f"状态: {decision.state}"
        )


class MBTITool(BaseCompanionTool):
    """MBTI 查询 Tool — 获取人格画像"""

    name = "companion_mbti"
    description = "Get MBTI personality profile"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        mbti_code = args.get("type", registry.mbti_type)
        profile = registry.mbti.get_profile(mbti_code)

        return (
            f"MBTI: {mbti_code} ({profile.type.nickname})\n"
            f"沟通风格: {profile.type.communication_style}\n"
            f"情绪表达: {profile.type.emotional_expression}\n"
            f"优势: {', '.join(profile.type.strengths[:3])}"
        )


class SceneTool(BaseCompanionTool):
    """场景查询 Tool — 获取适合当前时间的场景"""

    name = "companion_scene"
    description = "Get suitable scenes for current time and mood"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        from datetime import datetime
        hour = args.get("hour", datetime.now().hour)
        mood = args.get("mood", "idle")

        scenes = registry.scenes.get_suitable_scenes(hour, mood)
        if not scenes:
            return f"当前时间和心情没有特别合适的场景"

        lines = [f"- {s.name}: {s.prompt_hint}" for s in scenes[:5]]
        return f"合适的场景:\n" + "\n".join(lines)


class TrendingTool(BaseCompanionTool):
    """热搜查询 Tool — 获取缓存热点话题"""

    name = "companion_trending"
    description = "Get cached trending topics for conversation"

    def run(self, args: dict) -> str:
        registry = self.registry
        if not registry:
            return "Registry not initialized"

        topic = registry.trending.get_random_topic()
        if not topic:
            return "暂无热点话题"
        return f"热点话题: {topic}"
