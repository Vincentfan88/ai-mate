"""Mini-Agent Tool 适配器 — 将 companion 模块包装为 Mini-Agent Tool 子类。

每个适配器继承 mini_agent.tools.Tool，将 companion 的业务逻辑
暴露为 LLM 可调用的异步工具。
"""

import json
import os
from typing import Any, Optional

import httpx

from mini_agent.tools.base import Tool, ToolResult
from companion.modules.registry import CompanionRegistry


class CompanionStateTool(Tool):
    """查询 companion 的综合状态（情绪、关系、活人感、HMM、偏好、场景）。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_state"

    @property
    def description(self) -> str:
        return (
            "获取 AI 伴侣的当前综合状态，包括：情绪、当前时间、关系阶段、"
            "活人感八维度评分、HMM 状态机状态、偏好推断、场景推荐。"
            "在你需要了解自己当前状态时调用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> ToolResult:
        try:
            r = self._registry
            from datetime import datetime
            from companion.modules.extras import TimeContext

            emotion = r.emotion.get_current_emotion("time_passage")
            ctx = TimeContext.from_now()
            stage = r.relationship.get_current_stage()
            hours = ctx.hour

            liveness_scores = r.liveness.calculate_scores()
            liveness_overall = r.liveness.get_overall_score(liveness_scores)

            hmm_state = r.trigger.hmm.current_state if hasattr(r.trigger, "hmm") else "unknown"
            beliefs = r.memory.preference.get_active_beliefs(limit=3)
            belief_texts = [f"- {b.content} ({b.trust_score:.0%})" for b in beliefs] if beliefs else ["暂无"]
            rel_stats = r.relationship.get_stats()
            days = r.relationship.get_days_together()

            scenes = r.scenes.get_suitable_scenes(
                hour=hours,
                mood=hmm_state,
                relationship_multiplier_fn=r.relationship.get_scene_multiplier,
                top_k=3,
            )
            scene_texts = [f"- {s.name} (权重: {score})" for s, score in scenes] if scenes else ["暂无合适场景"]

            profile = r.mbti.get_profile(r.mbti_type)
            lines = [
                "=== 当前状态 ===",
                f"时间: {ctx.time_description}",
                f"HMM 状态: {hmm_state}",
                f"情绪: {emotion['emotion']} (强度: {emotion['intensity']})",
                f"关系: {stage.name_cn} (Lv.{stage.level}) — 在一起 {days} 天",
                f"  互动: {rel_stats['interactions']} 次 | 情绪深度: {rel_stats['emotional_depth']:.2f}",
                f"活人感: {liveness_overall:.0%}",
                f"  主动性: {liveness_scores.get('主动性', 0):.0%} | 一致性: {liveness_scores.get('一致性', 0):.0%}",
                f"  成长性: {liveness_scores.get('成长性', 0):.0%} | 情绪化: {liveness_scores.get('情绪化', 0):.0%}",
                f"  脆弱性: {liveness_scores.get('脆弱性', 0):.0%} | 身体存在感: {liveness_scores.get('身体存在感', 0):.0%}",
                f"  不可预测性: {liveness_scores.get('不可预测性', 0):.0%} | 依恋度: {liveness_scores.get('依恋度', 0):.0%}",
                f"MBTI: {profile.type.code} ({profile.type.nickname})",
                f"  风格: {profile.speech.tone_keywords}",
                "偏好推断:",
                *belief_texts,
                "场景 (含关系乘数):",
                *scene_texts,
            ]
            return ToolResult(success=True, content="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"获取状态失败: {e}")


class CompanionMemoryTool(Tool):
    """companion 记忆操作工具 — 记录/搜索/推断偏好。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_memory"

    @property
    def description(self) -> str:
        return (
            "操作 AI 伴侣的记忆系统。支持的动作：\n"
            "- record: 记录一条新记忆 (需提供 content, 可选 importance)\n"
            "- search: 搜索记忆 (需提供 query)\n"
            "- preferences: 从记忆推断用户偏好\n"
            "- recent: 获取最近对话 (可选 limit)"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["record", "search", "preferences", "recent"],
                    "description": "要执行的操作类型",
                },
                "content": {
                    "type": "string",
                    "description": "记录时的记忆内容 (action=record 时必需)",
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词 (action=search 时必需)",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量限制 (action=recent 时可选，默认3)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, content: str = "", query: str = "", limit: int = 3) -> ToolResult:
        try:
            r = self._registry
            if action == "record":
                if not content:
                    return ToolResult(success=False, content="", error="record 操作需要提供 content")
                r.memory.record(content)
                return ToolResult(success=True, content=f"已记录: {content}")
            elif action == "search":
                results = r.memory.search(query)
                if not results:
                    return ToolResult(success=True, content=f"未找到关于 '{query}' 的记忆")
                lines = [f"- {r['content']} (温度: {r.get('temperature', 0):.2f})" for r in results[:5]]
                return ToolResult(success=True, content=f"找到 {len(results)} 条记忆:\n" + "\n".join(lines))
            elif action == "preferences":
                prefs = r.memory.infer_preferences()
                inferences = prefs.get("inferences", [])
                if not inferences:
                    return ToolResult(success=True, content="还没有足够的信息推断偏好")
                return ToolResult(success=True, content="偏好推断:\n" + "\n".join(inferences))
            elif action == "recent":
                recent = r.memory.get_recent_conversations(limit)
                if not recent:
                    return ToolResult(success=True, content="暂无最近对话")
                lines = [f"- [{r.get('role', '?')}] {r['content']}" for r in recent]
                return ToolResult(success=True, content=f"最近 {len(recent)} 轮对话:\n" + "\n".join(lines))
            else:
                return ToolResult(success=False, content="", error=f"未知动作: {action}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"记忆操作失败: {e}")


class CompanionEmotionTool(Tool):
    """companion 情绪查询/更新工具。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_emotion"

    @property
    def description(self) -> str:
        return (
            "获取或更新 AI 伴侣的当前情绪状态。"
            "可以指定事件类型（如 time_passage, user_message, compliment 等）"
            "和对方的情绪来影响 AI 的情绪响应。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "触发情绪的事件类型（如 time_passage, user_message, compliment, argument 等）",
                },
                "user_emotion": {
                    "type": "string",
                    "description": "对方的情绪（如 happy, sad, angry 等），会影响回应的情绪色彩",
                },
            },
        }

    async def execute(self, event_type: str = "time_passage", user_emotion: Optional[str] = None) -> ToolResult:
        try:
            r = self._registry
            emotion = r.emotion.get_current_emotion(event_type, user_emotion)
            r.emotion.save_residue()
            return ToolResult(
                success=True,
                content=(
                    f"当前情绪: {emotion['emotion']}\n"
                    f"强度: {emotion['intensity']}\n"
                    f"语气: {emotion['tone_description']}"
                ),
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"获取情绪失败: {e}")


class CompanionTriggerTool(Tool):
    """companion 主动触发决策工具。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_trigger"

    @property
    def description(self) -> str:
        return (
            "AI 伴侣的主动联系决策系统。基于 Weibull 分布和 HMM 状态机"
            "计算是否应该主动联系对方。返回两阶段的拟人化决策："
            "想联系的理由（pull）和忍住的理由（hold_back）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hours_since_last_contact": {
                    "type": "number",
                    "description": "距离上次联系的小时数，用于计算触发概率",
                },
            },
        }

    async def execute(self, hours_since_last_contact: float = 12) -> ToolResult:
        try:
            r = self._registry
            decision = r.trigger.compute(hours_since_last_contact=hours_since_last_contact)
            return ToolResult(
                success=True,
                content=(
                    f"是否联系: {'是' if decision.should_trigger else '否'}\n"
                    f"想联系的理由: {decision.pull}\n"
                    f"忍住的理由: {decision.hold_back}\n"
                    f"冲动: {decision.nudge}\n"
                    f"状态: {decision.state}"
                ),
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"触发决策失败: {e}")


class CompanionMBTITool(Tool):
    """MBTI 人格画像查询工具。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_mbti"

    @property
    def description(self) -> str:
        return "获取 AI 伴侣或对方的 MBTI 人格画像，包括沟通风格、情绪表达方式、优势特征。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mbti_type": {
                    "type": "string",
                    "description": "MBTI 类型代码（如 ENFP, INTJ, ISFJ 等），不传则返回 AI 自身的画像",
                },
            },
        }

    async def execute(self, mbti_type: Optional[str] = None) -> ToolResult:
        try:
            r = self._registry
            code = mbti_type or r.mbti_type
            profile = r.mbti.get_profile(code)
            return ToolResult(
                success=True,
                content=(
                    f"MBTI: {code} ({profile.type.nickname})\n"
                    f"沟通风格: {profile.type.communication_style}\n"
                    f"情绪表达: {profile.type.emotional_expression}\n"
                    f"优势: {', '.join(profile.type.strengths[:3])}"
                ),
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"获取 MBTI 画像失败: {e}")


class CompanionSceneTool(Tool):
    """场景推荐工具。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_scene"

    @property
    def description(self) -> str:
        return "根据当前时间和心情推荐适合的互动场景，结合关系阶段进行加权匹配。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hour": {
                    "type": "integer",
                    "description": "当前小时 (0-23)，不传则自动使用当前时间",
                },
                "mood": {
                    "type": "string",
                    "description": "当前心情状态（如 idle, happy, sad, missing 等）",
                },
            },
        }

    async def execute(self, hour: Optional[int] = None, mood: str = "idle") -> ToolResult:
        try:
            r = self._registry
            from datetime import datetime
            h = hour if hour is not None else datetime.now().hour
            scenes = r.scenes.get_suitable_scenes(
                hour=h,
                mood=mood,
                relationship_multiplier_fn=r.relationship.get_scene_multiplier,
                top_k=5,
            )
            if not scenes:
                return ToolResult(success=True, content="当前时间和心情没有特别合适的场景")
            lines = [f"- {s.name}: {s.prompt_hint} (权重: {score:.2f})" for s, score in scenes[:5]]
            return ToolResult(success=True, content="合适的场景:\n" + "\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"获取场景推荐失败: {e}")


class CompanionFeishuTool(Tool):
    """飞书消息发送工具 — 让 LLM 主动发送飞书消息。"""

    def __init__(self, feishu_app_id: str = "", feishu_app_secret: str = ""):
        self._app_id = feishu_app_id or os.environ.get("FEISHU_APP_ID", "")
        self._app_secret = feishu_app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self._default_chat_id = os.environ.get("FEISHU_CHAT_ID", "")
        self._token: Optional[str] = None
        self._token_expire: float = 0

    @property
    def name(self) -> str:
        return "companion_feishu"

    @property
    def description(self) -> str:
        return (
            "发送消息到飞书。在主动触发场景下，生成回复后用此工具发送。"
            "如果不传 chat_id，默认发送到配置的会话。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "要发送的消息内容",
                },
                "chat_id": {
                    "type": "string",
                    "description": "飞书会话 ID（可选，不传则发到默认会话）",
                },
            },
            "required": ["message"],
        }

    async def execute(self, message: str, chat_id: str = "") -> ToolResult:
        try:
            if not self._app_id or not self._app_secret:
                return ToolResult(success=False, content="", error="飞书 Bot 未配置（缺少 app_id / app_secret）")

            cid = chat_id or self._default_chat_id
            if not cid:
                return ToolResult(success=False, content="", error="未指定 chat_id 且未配置默认会话")

            await self._ensure_token()

            content = json.dumps({"text": message})
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    params={"receive_id_type": "chat_id"},
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "receive_id": cid,
                        "msg_type": "text",
                        "content": content,
                    },
                )
                data = resp.json()
                if data.get("code") == 0:
                    return ToolResult(success=True, content="消息已发送到飞书")
                return ToolResult(success=False, content="", error=f"发送失败: {data.get('msg', 'unknown')}")

        except Exception as e:
            return ToolResult(success=False, content="", error=f"飞书发送失败: {e}")

    async def _ensure_token(self):
        """获取或刷新 tenant_access_token。"""
        import time
        now = time.time()
        if self._token and now < self._token_expire - 300:
            return
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            data = resp.json()
            self._token = data["tenant_access_token"]
            self._token_expire = now + data.get("expire", 7200)


class CompanionTrendingTool(Tool):
    """热点话题查询工具。"""

    def __init__(self, registry: CompanionRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "companion_trending"

    @property
    def description(self) -> str:
        return "获取缓存的热点话题，用于在对话中引入新鲜话题。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> ToolResult:
        try:
            r = self._registry
            topic = r.trending.get_random_topic()
            if not topic:
                return ToolResult(success=True, content="暂无热点话题")
            return ToolResult(success=True, content=f"热点话题: {topic}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"获取热点话题失败: {e}")
