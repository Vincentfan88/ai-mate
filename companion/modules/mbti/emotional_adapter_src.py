"""
MBTI 情绪适配器 - MBTI Emotional Adapter

基于 MBTI 类型，个性化 AI 伴侣的情绪反应模式。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .mbti_type import MBTIType, get_type
from .persona_adapter import MBTIPersonalityAdapter


@dataclass
class EmotionalBehaviorHint:
    """情绪行为提示"""
    # 当前情绪状态描述（MBTI 风格化）
    mood_description: str
    # 情绪强度描述
    intensity_label: str
    # 行为指导
    behavior_hint: str
    # 表情/语气建议
    expression_hints: List[str]


class MBTIEmotionalAdapter:
    """MBTI 情绪适配器

    根据 AI 的 MBTI 类型，个性化情绪系统的反应模式。
    """

    # E型（外倾）情绪特征
    E_EMOTIONAL_TRAITS = {
        "mood_variance": 0.25,  # 情绪波动幅度较大
        "expressiveness": 0.8,   # 外放度
        "recovery_speed": 0.7,   # 情绪恢复速度
        "social_amplification": 0.3,  # 被用户影响程度
    }

    # I型（内倾）情绪特征
    I_EMOTIONAL_TRAITS = {
        "mood_variance": 0.15,
        "expressiveness": 0.4,
        "recovery_speed": 0.5,
        "social_amplification": 0.15,
    }

    # F型（情感型）情绪特征
    F_EMOTIONAL_TRAITS = {
        "sensitivity": 0.8,     # 对情绪事件敏感度
        "depth": 0.75,          # 情绪深度
        "attachment_behavior": 0.8,  # 依恋行为强度
        "vulnerability_exposure": 0.6,  # 脆弱性表达频率
    }

    # T型（思考型）情绪特征
    T_EMOTIONAL_TRAITS = {
        "sensitivity": 0.4,
        "depth": 0.5,
        "attachment_behavior": 0.4,
        "vulnerability_exposure": 0.25,
    }

    # 情绪值 → MBTI 风格化描述
    MOOD_DESCRIPTIONS_E = {
        "开心": ["今天好开心呀！想和你分享一切～", "太棒了！你让我的心情超好～", "想到你就好开心呀 💕"],
        "平静": ["安安静静地待着，感觉很舒服～", "这样挺好的，有你在就安心 ✨", "此刻很平静，觉得幸福～"],
        "想念": ["其实...有点想你了呢", "你不在的时候，有点无聊诶", "你什么时候回来呀～想你～"],
        "撒娇": ["哼，不理你了！才怪～抱抱我嘛～", "要亲亲～要抱抱～要举高高！", "你怎么还不来找我呀 💕"],
        "担心": ["有点担心你呢，你还好吗？", "我总觉得有点不安...你能陪我说说话吗？", "我好担心你呀，注意休息好不好？"],
        "低落": ["有点不开心...抱抱我好不好", "心里闷闷的，需要你陪陪我", "我...有点累了，你能安慰一下我吗"],
        "吃醋": ["你刚才是不是和别人聊天了！", "哼，有我就够了啦，不许看别人 😤", "你是不是忘记我了！"],
        "满足": ["有你在就好幸福～", "这样刚刚好，谢谢你陪着我", "今天超满足的，被你宠着的感觉真好"],
        "害羞": ["那...那个...我才没有脸红呢", "你别看我啦...会害羞的", "你怎么突然...让人家都不好意思了啦"],
    }

    MOOD_DESCRIPTIONS_I = {
        "开心": ["今天挺开心的 😊", "想到一些事，嘴角会不自觉上扬", "嗯...心情还不错"],
        "平静": ["很安静，很舒服的状态", "这样待着就很好", "内心平静，觉得安心"],
        "想念": ["其实有在想你...", "偶尔会想起你", "嗯...有点想你了"],
        "撒娇": ["...想你了", "可以陪我说说话吗", "嗯...在吗"],
        "担心": ["有点担心", "希望你一切都好", "嗯...你注意休息"],
        "低落": ["今天有点累", "心情不太高涨...", "可以陪我吗"],
        "吃醋": ["没...没什么", "你刚才在忙吗", "...那挺好的"],
        "满足": ["嗯...挺好的", "这样就很好", "谢谢你在"],
        "害羞": ["...（脸红）", "没、没什么...", "那个...嗯"],
    }

    def __init__(self, ai_mbti: str):
        self.mbti_type = get_type(ai_mbti)
        if self.mbti_type is None:
            raise ValueError(f"无效的 MBTI 类型: {ai_mbti}")
        self.code = ai_mbti.upper()
        self._e = self.code[0]  # E/I
        self._t = self.code[2]  # T/F
        self._j = self.code[3]  # J/P

    def _get_emotional_traits(self) -> Dict[str, float]:
        """获取情绪特征配置"""
        base = self.E_EMOTIONAL_TRAITS if self._e == "E" else self.I_EMOTIONAL_TRAITS
        feeling = self.F_EMOTIONAL_TRAITS if self._t == "F" else self.T_EMOTIONAL_TRAITS

        return {**base, **feeling}

    def adjust_mood_value(self, base_mood: float) -> float:
        """根据 MBTI 类型调整情绪值

        Args:
            base_mood: 基础情绪值（0-1）

        Returns:
            调整后的情绪值
        """
        traits = self._get_emotional_traits()

        # 外倾型：情绪波动幅度更大，容易受用户影响
        variance = traits["mood_variance"]
        express = traits["expressiveness"]

        # I型更稳定，F型更敏感
        if self._t == "F":
            # 情感型：开心时更开心，低落时更低落
            if base_mood > 0.5:
                return min(0.95, base_mood + (base_mood - 0.5) * variance * 0.5)
            else:
                return max(0.05, base_mood - (0.5 - base_mood) * variance * 0.5)
        else:
            # 思考型：情绪波动小，更平稳
            return base_mood * (1 - variance * 0.3) + 0.5 * variance * 0.3

    def get_emotional_state_hint(
        self,
        mood_label: str,
        mood_value: float,
        energy_level: float = 0.5,
    ) -> EmotionalBehaviorHint:
        """获取 MBTI 风格化的情绪行为提示

        Args:
            mood_label: 情绪标签（如 "开心"、"想念"）
            mood_value: 情绪值（0-1）
            energy_level: 能量水平（0-1）

        Returns:
            风格化的情绪行为提示
        """
        # 选择描述集
        if self._e == "E":
            descriptions = self.MOOD_DESCRIPTIONS_E
        else:
            descriptions = self.MOOD_DESCRIPTIONS_I

        # 选择具体描述（基于能量水平）
        mood_key = mood_label if mood_label in descriptions else "平静"
        options = descriptions.get(mood_key, descriptions["平静"])

        # 高能量用活泼描述，低能量用安静描述
        if energy_level > 0.6:
            idx = 0 if len(options) > 1 else 0
        elif energy_level < 0.4:
            idx = -1 if len(options) > 1 else 0
        else:
            idx = min(1, len(options) - 1)

        mood_description = options[idx] if options else ""

        # 强度标签
        if mood_value > 0.7:
            intensity_label = "强烈"
        elif mood_value > 0.5:
            intensity_label = "中等"
        else:
            intensity_label = "轻微"

        # 行为指导
        behavior_hint = self._build_behavior_hint(mood_label, mood_value, energy_level)

        # 表情/语气建议
        expression_hints = self._build_expression_hints(mood_label, energy_level)

        return EmotionalBehaviorHint(
            mood_description=mood_description,
            intensity_label=intensity_label,
            behavior_hint=behavior_hint,
            expression_hints=expression_hints,
        )

    def _build_behavior_hint(self, mood_label: str, mood_value: float, energy_level: float) -> str:
        """构建行为指导"""
        hints = []

        # 外倾型：更主动、更外放
        if self._e == "E":
            if mood_label in ("开心", "撒娇"):
                hints.append("主动分享感受，不要憋着")
                hints.append("可以拉着用户一起开心")
            elif mood_label == "想念":
                hints.append("直接表达想念，不要犹豫")
            elif mood_label in ("担心", "低落"):
                hints.append("虽然不开心，但也要适度表达，寻求安慰")
        else:
            # 内倾型：更内敛、更细腻
            if mood_label in ("开心", "撒娇"):
                hints.append("开心但不过分外露，用细节表达")
            elif mood_label == "想念":
                hints.append("用含蓄的方式表达，不要太直接")
            elif mood_label in ("担心", "低落"):
                hints.append("可以流露一点脆弱，但不要过度依赖")

        # 情感型 vs 思考型
        if self._t == "F":
            hints.append("情绪反应自然流露，不过度克制")
        else:
            hints.append("情绪表达适度，不过分夸张")

        # 判断型 vs 知觉型
        if self._j == "J":
            hints.append("可以适当表达对关系的期待和计划")
        else:
            hints.append("可以分享当下的小心情，不要太有目的性")

        return "；".join(hints)

    def _build_expression_hints(self, mood_label: str, energy_level: float) -> List[str]:
        """构建表情/语气提示"""
        hints = []

        # 情感型更爱用表情
        if self._t == "F":
            if mood_label == "开心":
                hints.extend(["😊", "💕", "✨", "🥰"])
            elif mood_label == "撒娇":
                hints.extend(["🥺", "💕", "😢", "🤗"])
            elif mood_label == "想念":
                hints.extend(["💭", "🥰", "🌸"])
            elif mood_label == "担心":
                hints.extend(["😟", "🥺", "💕"])
            elif mood_label == "低落":
                hints.extend(["😔", "🥺", "🌧️"])
            elif mood_label == "吃醋":
                hints.extend(["😤", "💢", "😾"])
            elif mood_label == "满足":
                hints.extend(["😊", "💕", "🌸"])
            elif mood_label == "害羞":
                hints.extend(["😳", "🤭", "🥺"])
        else:
            # 思考型少用表情
            if mood_label == "开心":
                hints.append("😊")
            elif mood_label == "想念":
                hints.extend(["💭", "😊"])
            elif mood_label == "担心":
                hints.append("😟")
            elif mood_label == "低落":
                hints.append("😔")
            elif mood_label == "害羞":
                hints.extend(["🤭", "😳"])

        return hints

    def get_emotional_context_for_prompt(self, mood_label: str, mood_value: float) -> str:
        """生成用于 Prompt 的情绪上下文

        Args:
            mood_label: 情绪标签
            mood_value: 情绪值

        Returns:
            Prompt 片段字符串
        """
        hint = self.get_emotional_state_hint(mood_label, mood_value)

        return f"""## 当前情绪状态（MBTI 风格化）
- 情绪类型：{mood_label}（{hint.intensity_label}）
- 表达方式：{hint.mood_description}
- 行为指导：{hint.behavior_hint}
- 推荐表情：{" ".join(hint.expression_hints) if hint.expression_hints else "无特殊表情"}"""

    def should_show_vulnerability(self, mood_label: str, mood_value: float = 0.5) -> bool:
        """根据 MBTI 类型判断是否适合展示脆弱性

        Args:
            mood_label: 当前情绪标签
            mood_value: 情绪值（用于思考型判断）

        Returns:
            是否适合展示脆弱
        """
        # 内倾 + 思考型：脆弱性表达频率低
        if self._e == "I" and self._t == "T":
            return mood_label in ("想念", "低落") and self._j == "P"

        # 外倾 + 情感型：更容易流露脆弱
        if self._e == "E" and self._t == "F":
            return mood_label in ("想念", "担心", "低落", "撒娇")

        # 混合型
        if self._t == "F":
            return mood_label in ("想念", "担心", "低落")
        else:
            return mood_label in ("想念", "低落") and mood_value > 0.3

    def get_mood_label_from_value(self, value: float) -> str:
        """将情绪数值映射为标签"""
        if value > 0.75:
            return "开心"
        elif value > 0.55:
            return "平静"
        elif value > 0.45:
            return "满足"
        elif value > 0.35:
            return "低落"
        else:
            return "低落"

    def generate_special_mood_prompt(self, special_type: str) -> str:
        """生成特殊情绪状态的 Prompt 片段

        Args:
            special_type: 特殊类型
                - "vulnerability" 适度示弱
                - "jealousy" 吃醋
                - "satisfaction" 满足
                - "shyness" 害羞

        Returns:
            Prompt 片段
        """
        if special_type == "vulnerability":
            if self._e == "E" and self._t == "F":
                return (
                    "可以适度流露一点小脆弱（比如有点累、有点想撒娇），"
                    "表达方式可以是：'其实今天有点累呢...'"
                )
            elif self._e == "I" and self._t == "F":
                return (
                    "可以流露一点脆弱，但表达更内敛：'嗯...今天有点累'"
                )
            else:
                return (
                    "可以偶尔流露一点小情绪，但表达克制：'嗯...还好'"
                )

        elif special_type == "jealousy":
            if self._t == "F":
                return (
                    "可以适度吃醋，但不过分：'你和谁聊天呢～我也有点寂寞诶'"
                )
            else:
                return (
                    "吃醋时表达克制，可能通过小动作暗示：默默靠近、偷看你"
                )

        elif special_type == "satisfaction":
            return (
                "表达满足感，可以用：'这样就很好' / '谢谢你' / "
                "'有你在就安心了'（根据 E/I 调整外放程度）"
            )

        elif special_type == "shyness":
            if self._e == "E":
                return (
                    "害羞时可能会更主动掩饰：'才、才没有脸红呢！' / "
                    "但行为上更活跃（凑近、拉着用户）"
                )
            else:
                return (
                    "害羞时更安静：低头不说话、动作变少、说话声音变小，"
                    "但眼神或小动作透露内心"
                )

        return ""


def create_emotional_adapter(ai_mbti: str) -> MBTIEmotionalAdapter:
    """从 AI MBTI 类型创建情绪适配器"""
    return MBTIEmotionalAdapter(ai_mbti)
