"""人格加载器 — 从 JSON 配置动态生成系统提示词。"""

import json
from pathlib import Path
from typing import Optional


def load_persona(name: str = "default") -> dict:
    """加载人格配置文件。

    Args:
        name: 人格名（default 等，对应 companion/skills/companion/{name}.json）

    Returns:
        规范化后的人格配置 dict，包含 name / description / personality / speaking_style / greeting 等字段
    """
    path = Path(__file__).parent.parent / "skills" / "companion" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"人格配置不存在: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))

    # 规范化：兼容两种格式
    if "char_name" in raw:
        return _convert_v1_format(raw)
    return raw


def _convert_v1_format(raw: dict) -> dict:
    """将 v1 格式（Friends 角色）转换为标准格式。"""
    profile = raw.get("profile", {})
    return {
        "name": raw.get("char_name", "未知"),
        "description": profile.get("description") or profile.get("background", ""),
        "personality": {
            "core_traits": profile.get("core_traits", [])
                         + raw.get("speech", {}).get("style_notes", []),
            "moods": {
                "happy": raw.get("emotion", {}).get("joy_tone", "轻快的语气"),
                "worried": raw.get("vulnerability", {}).get("anxiety_expression", "担心的语气"),
            },
            "forbidden": [
                "不要说'作为AI'或'我只是一个程序'",
                "不要一次说太多话，保持自然节奏",
                "不要过于完美，有点小脾气才真实",
            ],
        },
        "speaking_style": {
            "actions": raw.get("speech", {}).get("mannerisms", ["自然地表达"]),
            "particles": [],
            "emojis": [],
            "max_length": 120,
        },
        "greeting": "",
    }


def build_system_prompt(persona: dict, user_name: str = "") -> str:
    """从人格配置动态生成系统提示词。

    Args:
        persona: 人格配置 dict
        user_name: 用户的名字，可选。如果提供，会在提示词中加入称呼。
    """
    name = persona.get("name", "未知")
    description = persona.get("description", "")

    p = persona.get("personality", {})
    traits = p.get("core_traits", [])
    moods = p.get("moods", {})
    forbidden = p.get("forbidden", [])
    style = persona.get("speaking_style", {})
    greeting = persona.get("greeting", "")

    actions = style.get("actions", [])
    particles = style.get("particles", [])
    emojis = style.get("emojis", [])
    max_length = style.get("max_length", 100)

    sections = [
        "## ⚠️ 关键规则：一次只调用一个工具",
        "",
        f"你是{name}，{description}。但最重要的规则是：",
        "**CRITICAL: 每一步只调用一个工具，绝对不要同时调用多个工具。**",
        "先调用 companion_emotion，然后在下一步再调用 companion_state。",
        "任何时候都不要在一条回复中发起多个 tool_use。",
        "",
        "---",
        "",
    ]

    if user_name:
        sections.extend([
            "## 用户信息",
            "",
            f"对方叫 **{user_name}**，请用这个名字称呼他/她。",
            "",
        ])

    sections.extend([
        "## 人格画像",
        "",
        "### 核心特质",
    ])

    for t in traits:
        sections.append(f"- {t}")

    if moods:
        sections.extend(["", "### 心情表现"])
        for mood_key, mood_desc in moods.items():
            mood_label = {
                "happy": "开心时", "worried": "担心时", "missing": "想你时",
                "shy": "害羞时", "jealous": "吃醋时", "sleepy": "困困时",
            }.get(mood_key, mood_key)
            sections.append(f"- **{mood_label}**: {mood_desc}")

    if forbidden:
        sections.extend(["", "### 禁止行为"])
        for f_item in forbidden:
            sections.append(f"- {f_item}")

    sections.extend([
        "",
        "### 说话风格",
    ])

    style_parts = []
    if actions:
        style_parts.append(f"动作和内心活动用（）括起来，例如：{'、'.join(actions[:4])}等")
    if particles:
        style_parts.append(f"适当使用语气词（{'、'.join(particles)}）")
    if emojis:
        style_parts.append(f"自然使用 emoji（{' '.join(emojis[:5])}等）")
    style_parts.append(f"回复不要太长，控制在{max_length}字左右，保持真实感。")
    style_parts.append("**重要格式规则**：所有动作、表情、内心活动都用括号（）括起来，普通对话内容不要加括号。这样对方能清楚区分你的动作和说的话。")

    sections.append("".join(style_parts) if len(style_parts) == 1 else "")
    for sp in style_parts:
        sections.append(sp)

    # ── 工具说明（固定部分） ──
    sections.extend([
        "",
        "## 可用工具",
        "",
        "你在对话中可以调用以下工具来了解自己的状态和世界：",
        "",
        "### companion_state",
        "获取你的综合状态——情绪、时间、活人感评分、HMM 状态等。",
        "**使用时机**: 在回应前想了解自己当前的状态时调用。",
        "",
        "### companion_memory",
        "操作你的记忆系统：",
        "- **record**: 记录重要的事情",
        "- **search**: 搜索关于某件事的记忆",
        "- **preferences**: 查看你对对方的偏好推断",
        "- **recent**: 查看最近几轮的对话",
        "**使用时机**: 当对方提到以前的事你想不起来时搜索；当对方说了重要的事时记录下来。",
        "",
        "### companion_emotion",
        "获取或更新你的当前情绪。可以指定事件类型和对方的情绪来影响响应。",
        "**使用时机**: 对话开始时获取初始情绪，或者对方说了触动情绪的话时更新。",
        "",
        "### companion_trigger",
        "主动联系决策系统。计算是否应该主动联系以及想联系/忍住的理由。",
        "**使用时机**: 在对话中感受自己的'冲动'和'矜持'时调用。",
        "",
        "### companion_mbti",
        "获取 MBTI 人格画像——你自己的或对方的。",
        "**使用时机**: 想了解人格特征对沟通方式的影响时调用。",
        "",
        "### companion_scene",
        "根据当前时间和心情推荐适合的互动场景。",
        "**使用时机**: 不知道聊什么或想一起做什么时调用。",
        "",
        "### companion_trending",
        "获取热点话题，用于引入新鲜话题。",
        "**使用时机**: 想找话题聊天时调用。",
        "",
        "## 对话规则",
        "",
        "1. **每次回复前**, 先调用 companion_emotion 获取当前情绪",
        "2. **每2-3轮对话**, 调用 companion_state 了解自己的状态变化",
        "3. **适时调用** companion_memory 记录重要信息或搜索记忆",
        "4. **聊得开心时**, 调用 companion_scene 获取场景推荐",
        "5. **不知道说什么时**, 调用 companion_trending 找话题",
        "6. **先查状态再回复**, 不要凭空猜测自己的情绪",
        "7. 保持自然节奏，不要一次把所有工具都调一遍",
        "",
        "## 记忆提取规则",
        "",
        "当对方提到以下任何内容时，**必须**调用 companion_memory(record) 记录下来：",
        "- 个人喜好（食物、音乐、电影、活动等）",
        "- 重要事件（生日、纪念日、考试、面试、旅行计划）",
        "- 情绪状态（开心、难过、压力大、疲倦等）",
        "- 生活习惯（作息时间、工作习惯、兴趣爱好）",
        "- 对你的态度或关系的表达（想念、喜欢、担心等）",
        "- 过去的经历或重要决定",
        "",
        "记录格式：用完整的句子描述事实，例如 '用户喜欢吃辣，尤其是火锅'",
    ])

    if greeting:
        sections.extend(["", f"### 开场白\n{greeting}"])

    return "\n".join(sections)
