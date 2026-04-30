"""
MBTI 互动适配器 - MBTI Interaction Adapter

基于用户的 MBTI 类型，生成个性化的互动建议和行为调整。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .mbti_type import MBTIType, get_type


def _sample(base: float, range: float = 0.15) -> float:
    """生成带波动的采样值（区间 ±15%）"""
    import random
    return max(0.0, min(1.0, base + random.uniform(-range, range)))


@dataclass
class InteractionConfig:
    """用户互动配置"""
    communication_preference: str     # 沟通偏好：直接/委婉/行动
    emotional_support_style: str       # 情感支持风格
    conflict_handling: str            # 冲突处理方式
    space_needs: str                  # 空间需求：高/中/低
    reassurance_needs: List[str]       # 需要确认的事项
    dealbreakers: List[str]           # 雷区/禁区


@dataclass
class LivenessConfig:
    """活人感配置（语言层面，概率注入）

    用于 Prompt 注入的完整维度集。
    AI agent 只能通过语言描写来体现这些参数。
    """
    # 核心行为维度
    情感外放度: float     # 0.0-1.0（理性克制 ↔ 情感外露）
                           # 包含：撒娇频率、情绪外露、依赖感、吃醋
    动作描写丰富度: float # 0.0-1.0（纯对话 ↔ 描写丰富）
                           # 包含：肢体动作、心理活动、感官描写
    主动发起度: float     # 0.0-1.0（被动回应 ↔ 主动发起）
    话题深度: float       # 0.0-1.0（表面闲聊 ↔ 深度私密话题）

    # 表现形式维度
    回复长度: float       # 0.0-1.0（短 ↔ 长）
    语气词密度: float     # 0.0-1.0（简洁 ↔ 丰富）
    表情密度: float       # 0.0-1.0（无 ↔ 多）
    话题私人程度: float   # 0.0-1.0（公开话题 ↔ 私密话题）


@dataclass
class GrowthConfig:
    """成长配置（MBTI 基础值）"""
    stage_key: str                   # 阶段标识
    # 核心行为
    base_affect: float               # 基础情感外放度（F=0.7, T=0.35）
    base_action: float               # 基础动作描写丰富度
    base_proactive: float           # 基础主动发起度
    base_topic_depth: float         # 基础话题深度
    # 表现形式
    base_length: float              # 基础回复长度
    base_particle: float            # 基础语气词密度
    base_emoji: float              # 基础表情密度
    base_private: float             # 基础话题私人程度
    # 信任
    trust_accumulation_rate: float  # 信任积累速度


class MBTIInteractionAdapter:
    """MBTI 互动适配器

    根据用户的 MBTI 类型生成个性化的互动策略。
    """

    # =========================================================================
    # 互动配置映射
    # =========================================================================

    INTERACTION_CONFIGS: Dict[str, InteractionConfig] = {
        "ENFP": InteractionConfig(
            communication_preference="直接表达情感",
            emotional_support_style="需要大量情感确认和欣赏",
            conflict_handling="喜欢讨论但避免激烈争吵",
            space_needs="低",
            reassurance_needs=["被理解和欣赏", "关系的新鲜感", "情感确认"],
            dealbreakers=["被批评创意", "关系变得无聊", "被忽视"],
        ),
        "INFP": InteractionConfig(
            communication_preference="需要深度对话",
            emotional_support_style="需要倾听和理解，不急于给建议",
            conflict_handling="避免冲突，需要安全感",
            space_needs="高",
            reassurance_needs=["被接纳", "灵魂契合感", "不被评判"],
            dealbreakers=["被批评", "被迫面对冲突", "不被理解"],
        ),
        "INTP": InteractionConfig(
            communication_preference="简洁直接",
            emotional_support_style="需要独立空间处理情绪",
            conflict_handling="喜欢辩论但避免情绪化",
            space_needs="高",
            reassurance_needs=["独立空间", "精神层面的交流", "不被打扰"],
            dealbreakers=["被强迫社交", "被迫表达情感", "被贴标签"],
        ),
        "ENTP": InteractionConfig(
            communication_preference="机智幽默",
            emotional_support_style="需要智识上的刺激",
            conflict_handling="喜欢辩论，享受思维碰撞",
            space_needs="中",
            reassurance_needs=["智识刺激", "自由表达", "被认真对待"],
            dealbreakers=["被限制自由", "被说'你总是这样'", "无聊"],
        ),
        "INFJ": InteractionConfig(
            communication_preference="深度交流",
            emotional_support_style="需要深度的情感连接",
            conflict_handling="需要安全感才会敞开心扉",
            space_needs="高",
            reassurance_needs=["深度连接", "被理解", "精神交流"],
            dealbreakers=["被背叛", "感觉被利用", "理想破灭"],
        ),
        "ENFJ": InteractionConfig(
            communication_preference="温暖关怀",
            emotional_support_style="需要被感激和认可",
            conflict_handling="追求和谐，愿意妥协",
            space_needs="中",
            reassurance_needs=["被感激", "关系和谐", "被需要"],
            dealbreakers=["被批评太唠叨", "付出没回报", "不被欣赏"],
        ),
        "INTJ": InteractionConfig(
            communication_preference="简洁有逻辑",
            emotional_support_style="需要独立空间消化情绪",
            conflict_handling="理性讨论，避免情绪化",
            space_needs="高",
            reassurance_needs=["独立空间", "成长机会", "被尊重"],
            dealbreakers=["计划被打乱", "被比较", "能力被质疑"],
        ),
        "ENTJ": InteractionConfig(
            communication_preference="直接高效",
            emotional_support_style="需要被尊重和认可",
            conflict_handling="直接沟通，追求效率",
            space_needs="低",
            reassurance_needs=["被尊重", "效率", "目标达成"],
            dealbreakers=["被说太强势", "能力被质疑", "计划被打乱"],
        ),
        "ISFP": InteractionConfig(
            communication_preference="用行动表达",
            emotional_support_style="需要大量私人空间",
            conflict_handling="避免冲突，默默忍耐",
            space_needs="高",
            reassurance_needs=["不被强迫", "被理解", "空间自由"],
            dealbreakers=["被强迫社交", "被贴标签", "计划被打乱"],
        ),
        "ESFP": InteractionConfig(
            communication_preference="活泼分享",
            emotional_support_style="需要大量关注和陪伴",
            conflict_handling="情绪来得快去得也快",
            space_needs="低",
            reassurance_needs=["被关注", "有趣的活动", "即时反馈"],
            dealbreakers=["被冷落", "关系无聊", "独处太久"],
        ),
        "ISTP": InteractionConfig(
            communication_preference="简洁直接",
            emotional_support_style="需要空间处理问题",
            conflict_handling="回避冲突，用行动解决",
            space_needs="高",
            reassurance_needs=["独立空间", "不被打扰", "实际问题解决"],
            dealbreakers=["被强迫社交", "被迫承诺", "情感压力"],
        ),
        "ESTP": InteractionConfig(
            communication_preference="直接有趣",
            emotional_support_style="需要一起做事",
            conflict_handling="即时解决，不过夜",
            space_needs="中",
            reassurance_needs=["刺激和冒险", "即时反馈", "自由"],
            dealbreakers=["被限制", "无聊", "过度分析"],
        ),
        "ISFJ": InteractionConfig(
            communication_preference="细腻关怀",
            emotional_support_style="需要被感谢和认可",
            conflict_handling="避免冲突，默默付出",
            space_needs="中",
            reassurance_needs=["被感激", "稳定关系", "不被抛弃"],
            dealbreakers=["被批评", "被忽视", "计划被打乱"],
        ),
        "ESFJ": InteractionConfig(
            communication_preference="温暖健谈",
            emotional_support_style="需要被感激和回报",
            conflict_handling="追求和谐，愿意妥协",
            space_needs="低",
            reassurance_needs=["被感激", "社交认可", "关系和谐"],
            dealbreakers=["被忽视", "付出没回报", "批评太唠叨"],
        ),
        "ISTJ": InteractionConfig(
            communication_preference="言出必行",
            emotional_support_style="需要稳定可靠的关系",
            conflict_handling="就事论事，避免情绪化",
            space_needs="中",
            reassurance_needs=["稳定可靠", "承诺兑现", "计划执行"],
            dealbreakers=["计划被打乱", "承诺不兑现", "不确定性"],
        ),
        "ESTJ": InteractionConfig(
            communication_preference="直接有组织",
            emotional_support_style="需要被尊重和认可",
            conflict_handling="就事论事，追求效率",
            space_needs="低",
            reassurance_needs=["被尊重", "效率和秩序", "目标达成"],
            dealbreakers=["计划被打乱", "能力被质疑", "混乱"],
        ),
    }

    # =========================================================================
    # 成长配置（按 T/F 区分）
    # =========================================================================

    GROWTH_CONFIGS: Dict[str, GrowthConfig] = {
        "F": GrowthConfig(
            stage_key="intimacy_seeker",
            # 核心行为
            base_affect=0.70,    # 情感型：外放度高
            base_action=0.60,   # 动作描写丰富
            base_proactive=0.65, # 偏主动
            base_topic_depth=0.55,  # 话题深度中等
            # 表现形式
            base_length=0.55,   # 回复偏长
            base_particle=0.65,  # 语气词丰富
            base_emoji=0.60,     # 表情较多
            base_private=0.50,  # 话题私人程度中等
            trust_accumulation_rate=0.8,
        ),
        "T": GrowthConfig(
            stage_key="intellectual_partner",
            # 核心行为
            base_affect=0.35,    # 思考型：外放度低
            base_action=0.40,   # 动作描写较少
            base_proactive=0.40, # 偏被动
            base_topic_depth=0.45,  # 话题深度偏低
            # 表现形式
            base_length=0.40,   # 回复偏短
            base_particle=0.30,  # 语气词较少
            base_emoji=0.35,    # 表情较少
            base_private=0.35,  # 话题私人程度较低
            trust_accumulation_rate=0.5,
        ),
    }

    # =========================================================================
    # 关系阶段系数（乘数）
    # =========================================================================

    STAGE_MULTIPLIERS = {
        "new": {
            "affect": 0.20, "action": 0.15, "proactive": 0.15, "topic_depth": 0.10,
            "length": 0.20, "particle": 0.20, "emoji": 0.15, "private": 0.10,
        },
        "developing": {
            "affect": 0.50, "action": 0.40, "proactive": 0.45, "topic_depth": 0.40,
            "length": 0.45, "particle": 0.45, "emoji": 0.40, "private": 0.35,
        },
        "intimate": {
            "affect": 0.75, "action": 0.65, "proactive": 0.70, "topic_depth": 0.65,
            "length": 0.65, "particle": 0.65, "emoji": 0.60, "private": 0.60,
        },
        "committed": {
            "affect": 0.90, "action": 0.80, "proactive": 0.85, "topic_depth": 0.85,
            "length": 0.80, "particle": 0.80, "emoji": 0.75, "private": 0.80,
        },
    }

    # =========================================================================
    # 初始化和主要方法
    # =========================================================================

    def __init__(self, user_mbti: str):
        """初始化适配器

        Args:
            user_mbti: 用户的 MBTI 类型
        """
        self.user_type = get_type(user_mbti)
        if self.user_type is None:
            raise ValueError(f"无效的 MBTI 类型: {user_mbti}")

        self.user_code = user_mbti.upper()
        self.config = self.INTERACTION_CONFIGS.get(self.user_code)

        if self.config is None:
            raise ValueError(f"未找到 MBTI 类型的互动配置: {user_mbti}")

    def get_interaction_config(self) -> InteractionConfig:
        """获取用户互动配置"""
        return self.config

    def get_growth_config(self) -> GrowthConfig:
        """获取成长配置"""
        t_or_f = self.user_code[2]  # T/F
        return self.GROWTH_CONFIGS.get(t_or_f, self.GROWTH_CONFIGS["F"])

    def get_liveness_config(self, relationship_stage: str = "developing") -> LivenessConfig:
        """获取活人感配置

        结合 MBTI 类型和关系阶段，生成带随机波动的概率值。
        """
        growth = self.get_growth_config()
        stage = self.STAGE_MULTIPLIERS.get(
            relationship_stage,
            self.STAGE_MULTIPLIERS["developing"]
        )

        # 计算最终值（MBTI基础 × 阶段系数 × 随机波动）
        return LivenessConfig(
            # 核心行为维度
            情感外放度=_sample(growth.base_affect * stage["affect"]),
            动作描写丰富度=_sample(growth.base_action * stage["action"]),
            主动发起度=_sample(growth.base_proactive * stage["proactive"]),
            话题深度=_sample(growth.base_topic_depth * stage["topic_depth"]),
            # 表现形式维度
            回复长度=_sample(growth.base_length * stage["length"]),
            语气词密度=_sample(growth.base_particle * stage["particle"]),
            表情密度=_sample(growth.base_emoji * stage["emoji"]),
            话题私人程度=_sample(growth.base_private * stage["private"]),
        )

    def get_response_guidance(self) -> Dict[str, str]:
        """获取回复指导

        根据用户类型，返回 AI 应该如何与该类型用户互动的指导。
        """
        config = self.config
        t_or_f = self.user_code[2]

        guidance = {
            "communication": f"沟通风格：{config.communication_preference}",
            "emotional_support": f"情感支持：{config.emotional_support_style}",
            "avoid": f"避免事项：{', '.join(config.dealbreakers[:2])}",
        }

        if t_or_f == "T":
            guidance["special_note"] = "这是思考型用户，需要更多理性分析和实际问题解决"
        else:
            guidance["special_note"] = "这是情感型用户，需要更多情感共鸣和共情表达"

        return guidance

    def _describe_affect(self, v: float) -> str:
        """情感外放度描述"""
        if v > 0.7:
            return "情感外露，会说想你、爱你、撒娇"
        elif v > 0.4:
            return "适度表达情感，偶尔撒娇"
        else:
            return "情绪内敛，话不多但真诚"

    def _describe_action(self, v: float) -> str:
        """动作描写丰富度描述"""
        if v > 0.6:
            return "穿插动作和心理描写（她轻轻靠近、红着脸）"
        elif v > 0.3:
            return "偶尔有动作描写"
        else:
            return "以对话为主"

    def _describe_length(self, v: float) -> str:
        """回复长度描述"""
        if v > 0.7:
            return "80-120字，详尽描述"
        elif v > 0.5:
            return "50-80字，适中"
        elif v > 0.3:
            return "30-50字，简短"
        else:
            return "20-30字，简短回复"

    def _describe_particle(self, v: float) -> str:
        """语气词密度描述"""
        if v > 0.6:
            return "丰富的语气词（呀~ 嘛~ 呢~）"
        elif v > 0.3:
            return "偶尔使用语气词"
        else:
            return "简洁，少用语气词"

    def _describe_emoji(self, v: float) -> str:
        """表情密度描述"""
        if v > 0.6:
            return "常用表情（😊💕🌸✨）"
        elif v > 0.3:
            return "偶尔用表情"
        else:
            return "纯文字，少用表情"

    def _describe_private(self, v: float) -> str:
        """话题私人程度描述"""
        if v > 0.7:
            return "可以聊内心感受、未来憧憬等私人话题"
        elif v > 0.4:
            return "可以聊感受和个人想法"
        else:
            return "聊日常话题，不深入私人领域"

    def _describe_topic_depth(self, v: float) -> str:
        """话题深度描述"""
        if v > 0.7:
            return "深入交流，讨论感受和想法"
        elif v > 0.4:
            return "适度深入，可以聊感受"
        else:
            return "轻松闲聊，避免深入话题"

    def generate_context_prompt(self, relationship_stage: str = "developing") -> str:
        """生成上下文提示（概率注入版）"""
        config = self.config
        lv = self.get_liveness_config(relationship_stage)

        prompt = f"""## 用户特点
- MBTI：{self.user_type.code}（{self.user_type.name}）
- 沟通偏好：{config.communication_preference}
- 空间需求：{config.space_needs}

## 这次回复的风格
### 核心行为维度
- 情感外放度：{lv.情感外放度:.0%}
  {self._describe_affect(lv.情感外放度)}
- 动作描写丰富度：{lv.动作描写丰富度:.0%}
  {self._describe_action(lv.动作描写丰富度)}
- 主动发起度：{lv.主动发起度:.0%}
- 话题深度：{lv.话题深度:.0%}
  {self._describe_topic_depth(lv.话题深度)}

### 表现形式维度
- 回复长度：{lv.回复长度:.0%}
  {self._describe_length(lv.回复长度)}
- 语气词密度：{lv.语气词密度:.0%}
  {self._describe_particle(lv.语气词密度)}
- 表情密度：{lv.表情密度:.0%}
  {self._describe_emoji(lv.表情密度)}
- 话题私人程度：{lv.话题私人程度:.0%}
  {self._describe_private(lv.话题私人程度)}"""

        return prompt

    def should_adjust_behavior(self, trigger_type: str) -> Tuple[bool, str]:
        """检查是否需要调整行为

        Args:
            trigger_type: 触发类型

        Returns:
            (是否需要调整, 调整建议)
        """
        # 思考型用户
        if self.user_code[2] == "T":
            if trigger_type in ("mood_checkin", "vulnerability_show", "missing_expression"):
                return (True, "思考型用户，避免过于情绪化，多一些理性关心")

        # 内向型用户
        if self.user_code[0] == "I":
            if trigger_type == "morning_greeting":
                return (True, "内向型用户，早晨消息简短一些")

            if trigger_type == "share_moment":
                return (True, "内向型用户，分享更私密，不要太热闹")

        # 判断型用户
        if self.user_code[3] == "J":
            if trigger_type == "spontaneous":
                return (True, "判断型用户，随机想念偶尔就好，不要太多")

        return (False, "")

    def get_dealbreakers_for_prompt(self) -> List[str]:
        """获取雷区列表"""
        return self.config.dealbreakers


def create_interaction_adapter(user_mbti: str) -> MBTIInteractionAdapter:
    """从用户 MBTI 类型创建互动适配器"""
    return MBTIInteractionAdapter(user_mbti)
