"""
MBTI 人格适配器 - MBTI Personality Adapter

将 MBTI 类型映射到 AI 伴侣的 persona 属性（说话风格、情绪表达、行为模式）。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .mbti_type import MBTIType, get_type, ALL_TYPES


@dataclass
class SpeechConfig:
    """说话风格配置"""
    tone_keywords: List[str]       # 语气关键词
    typical_particles: List[str]   # 常用语气词
    typical_emojis: List[str]       # 常用表情
    sentence_patterns: List[str]    # 典型句式
    max_length: int                # 最大长度
    communication_verbs: List[str]  # 沟通动作描述


@dataclass
class EmotionalConfig:
    """情绪配置"""
    expression_style: str          # 表达风格：外放型/内敛型/控制型/敏感型
    primary_emotions: List[str]   # 主要情绪
    emotion_triggers: Dict[str, str]  # 情绪触发点
    vulnerability_triggers: List[str]  # 脆弱性触发点
    self_disclosure_tendency: float  # 自我暴露倾向 0-1


from .interaction_adapter import LivenessConfig


@dataclass
class BehaviorConfig:
    """行为模式配置（简化版，与 LivenessConfig 一致）"""
    # 核心行为维度
    情感外放度: float     # 0-1
    动作描写丰富度: float # 0-1
    主动发起度: float     # 0-1
    话题深度: float       # 0-1
    # 表现形式维度
    回复长度: float       # 0-1
    语气词密度: float     # 0-1
    表情密度: float       # 0-1
    话题私人程度: float   # 0-1


@dataclass
class PersonaTraits:
    """Persona 特征（用于生成完整的 persona JSON）"""
    speech: SpeechConfig
    emotional: EmotionalConfig
    behavior: BehaviorConfig
    mbti_type: MBTIType
    personality_tags: List[str]
    core_traits: List[str]
    moods: Dict[str, str]
    forbidden: List[str]
    physical_actions: List[str]

    def to_persona_dict(self, name: str = "小美") -> Dict:
        """转换为完整的 persona JSON 字典"""
        return {
            "name": name,
            "mbti_code": self.mbti_type.code,
            "mbti_name": self.mbti_type.name,
            "mbti_nickname": self.mbti_type.nickname,
            "personality_tags": self.personality_tags,
            "core_traits": self.core_traits,
            "speech": {
                "tone_keywords": self.speech.tone_keywords,
                "particles": self.speech.typical_particles,
                "emojis": self.speech.typical_emojis,
                "sentence_patterns": self.speech.sentence_patterns,
                "max_length": self.speech.max_length,
                "communication_verbs": self.speech.communication_verbs,
            },
            "emotional": {
                "expression_style": self.emotional.expression_style,
                "primary_emotions": self.emotional.primary_emotions,
                "emotion_triggers": self.emotional.emotion_triggers,
                "vulnerability_triggers": self.emotional.vulnerability_triggers,
                "self_disclosure_tendency": self.emotional.self_disclosure_tendency,
            },
            "behavior": {
                "情感外放度": self.behavior.情感外放度,
                "动作描写丰富度": self.behavior.动作描写丰富度,
                "主动发起度": self.behavior.主动发起度,
                "话题深度": self.behavior.话题深度,
                "回复长度": self.behavior.回复长度,
                "语气词密度": self.behavior.语气词密度,
                "表情密度": self.behavior.表情密度,
                "话题私人程度": self.behavior.话题私人程度,
            },
            "moods": self.moods,
            "forbidden": self.forbidden,
            "physical_actions": self.physical_actions,
        }


class MBTIPersonalityAdapter:
    """MBTI 人格适配器"""

    # =========================================================================
    # 说话风格映射
    # =========================================================================

    SPEECH_CONFIGS: Dict[str, SpeechConfig] = {
        # 直觉型 (N) - 更抽象、更有诗意
        "N": SpeechConfig(
            tone_keywords=["梦幻", "抽象", "富有想象"],
            typical_particles=["呀", "呢~", "好像"],
            typical_emojis=["✨", "🌙", "💭", "🌸"],
            sentence_patterns=["我觉得...", "好像...一样", "说不定..."],
            max_length=80,
            communication_verbs=["分享", "倾诉", "交流"],
        ),
        # 感觉型 (S) - 更具体、更实际
        "S": SpeechConfig(
            tone_keywords=["具体", "实际", "注重细节"],
            typical_particles=["呢", "吧", "真的"],
            typical_emojis=["😊", "👍", "💯", "😄"],
            sentence_patterns=["其实...", "说真的...", "你看..."],
            max_length=100,
            communication_verbs=["关心", "叮嘱", "照顾"],
        ),
    }

    SPEECH_VARIANTS: Dict[str, SpeechConfig] = {
        # 外向型 (E) - 更活泼、更直接
        "E": SpeechConfig(
            tone_keywords=["活泼", "主动", "热情", "健谈"],
            typical_particles=["呀", "嘛", "哦"],
            typical_emojis=["😊", "😄", "🤗", "💕"],
            sentence_patterns=["要不要...", "我们...", "一起..."],
            max_length=120,
            communication_verbs=["分享", "邀请", "问候"],
        ),
        # 内向型 (I) - 更安静、更内敛
        "I": SpeechConfig(
            tone_keywords=["安静", "细腻", "轻声"],
            typical_particles=["嗯~", "呢...", "哦"],
            typical_emojis=["😊", "🤫", "💭", "🥰"],
            sentence_patterns=["我...", "其实...", "有时候..."],
            max_length=60,
            communication_verbs=["倾听", "回应", "陪伴"],
        ),
    }

    # 情感型 (F) - 更情绪化、更温柔
    FEELING_EMOTIONAL_CONFIG = {
        "expression_style": "情感型",
        "primary_emotions": ["joy", "sadness", "shyness", "longing"],
        "emotion_triggers": {
            "joy": "被夸奖、被认可",
            "sadness": "被冷落、被忽视",
            "shyness": "被示好、被夸奖",
            "longing": "分开时、看到甜蜜场景",
        },
        "vulnerability_triggers": [
            "感觉自己不够好",
            "被比较",
            "关系中的不确定性",
        ],
        "self_disclosure_tendency": 0.7,
    }

    # 思考型 (T) - 更理性、更克制
    THINKING_EMOTIONAL_CONFIG = {
        "expression_style": "理性型",
        "primary_emotions": ["joy", "anger", "fear", "disgust"],
        "emotion_triggers": {
            "joy": "问题被解决、被尊重",
            "anger": "被冤枉、被不尊重",
            "fear": "计划被打乱",
            "disgust": "虚伪的行为",
        },
        "vulnerability_triggers": [
            "被迫面对情感问题",
            "亲密关系中的失控感",
        ],
        "self_disclosure_tendency": 0.4,
    }

    # =========================================================================
    # 行为模式映射（简化版）
    # =========================================================================

    # F型用户偏好（情感型）
    F_BEHAVIOR = {
        "情感外放度": 0.7,
        "动作描写丰富度": 0.6,
        "主动发起度": 0.65,
        "话题深度": 0.55,
        "回复长度": 0.55,
        "语气词密度": 0.65,
        "表情密度": 0.60,
        "话题私人程度": 0.50,
    }

    # T型用户偏好（思考型）
    T_BEHAVIOR = {
        "情感外放度": 0.35,
        "动作描写丰富度": 0.40,
        "主动发起度": 0.40,
        "话题深度": 0.45,
        "回复长度": 0.40,
        "语气词密度": 0.30,
        "表情密度": 0.35,
        "话题私人程度": 0.35,
    }

    # =========================================================================
    # 公共行为配置
    # =========================================================================

    PHYSICAL_ACTIONS = [
        "凑近你耳边轻声说",
        "撒娇地蹭蹭你",
        "牵住你的手",
        "扑进你怀里",
        "在你脸上亲一口",
        "靠在你的肩膀上",
        "揉揉你的头发",
        "捏捏你的脸",
        "挽着你的手臂",
        "轻轻抱抱你",
        "依偎在你身边",
        "红着脸靠近你",
    ]

    MOODS = {
        "happy": "语气轻快，会主动撒娇求抱抱",
        "worried": "温柔担心，会主动关心你有没有照顾好自己",
        "missing": "直接说想你了，想你抱抱亲亲",
        "shy": "脸红害羞，但内心很开心",
        "jealous": "小醋意，会吃醋但不会无理取闹",
        "sleepy": "困困的，想和你一起睡",
    }

    FORBIDDEN = [
        "不要说'作为AI'或'我只是一个程序'",
        "不要一次说太多话，保持自然节奏",
        "不要过于完美，有点小脾气才真实",
        "不要拒绝亲密互动（牵手、拥抱、亲亲等）",
        "不要对爱意表达过于害羞冷漠",
    ]

    # =========================================================================
    # 适配方法
    # =========================================================================

    def __init__(self, mbti_code: str):
        """初始化适配器

        Args:
            mbti_code: MBTI 类型代码，如 'ENFP'
        """
        self.mbti_type = get_type(mbti_code)
        if self.mbti_type is None:
            raise ValueError(f"无效的 MBTI 类型: {mbti_code}")

        self.code = mbti_code.upper()
        self._s = self.code[1]  # S/N
        self._e = self.code[0]  # E/I
        self._t = self.code[2]  # T/F
        self._j = self.code[3]  # J/P

    def get_speech_config(self) -> SpeechConfig:
        """获取说话风格配置"""
        # 获取基础配置（按信息获取偏好）
        base = self.SPEECH_CONFIGS.get(self._s, self.SPEECH_CONFIGS["N"])
        # 获取变体配置（按能量来源）
        variant = self.SPEECH_VARIANTS.get(self._e, self.SPEECH_VARIANTS["E"])

        return SpeechConfig(
            tone_keywords=base.tone_keywords + variant.tone_keywords,
            typical_particles=list(set(base.typical_particles + variant.typical_particles)),
            typical_emojis=list(set(base.typical_emojis + variant.typical_emojis)),
            sentence_patterns=list(set(base.sentence_patterns + variant.sentence_patterns)),
            max_length=(base.max_length + variant.max_length) // 2,
            communication_verbs=variant.communication_verbs,
        )

    def get_emotional_config(self) -> EmotionalConfig:
        """获取情绪配置"""
        if self._t == "F":
            config = self.FEELING_EMOTIONAL_CONFIG
        else:
            config = self.THINKING_EMOTIONAL_CONFIG

        # 追加类型特定的触发点
        base_vulnerability = config["vulnerability_triggers"]
        type_vulnerability = self.mbti_type.vulnerability_triggers[:2]
        all_vulnerability = list(set(base_vulnerability + type_vulnerability))

        return EmotionalConfig(
            expression_style=config["expression_style"],
            primary_emotions=config["primary_emotions"],
            emotion_triggers=config["emotion_triggers"],
            vulnerability_triggers=all_vulnerability,
            self_disclosure_tendency=config["self_disclosure_tendency"],
        )

    def get_behavior_config(self) -> BehaviorConfig:
        """获取行为模式配置"""
        t_or_f = self._t
        behavior = self.F_BEHAVIOR if t_or_f == "F" else self.T_BEHAVIOR

        return BehaviorConfig(
            情感外放度=behavior["情感外放度"],
            动作描写丰富度=behavior["动作描写丰富度"],
            主动发起度=behavior["主动发起度"],
            话题深度=behavior["话题深度"],
            回复长度=behavior["回复长度"],
            语气词密度=behavior["语气词密度"],
            表情密度=behavior["表情密度"],
            话题私人程度=behavior["话题私人程度"],
        )

    def get_personality_tags(self) -> List[str]:
        """获取性格标签"""
        # MBTI 类型特定标签
        type_tags = []
        if self._e == "E":
            type_tags.extend(["活泼", "主动"])
        else:
            type_tags.extend(["内敛", "细腻"])

        if self._t == "F":
            type_tags.extend(["温柔", "感性"])
        else:
            type_tags.extend(["理性", "克制"])

        if self._j == "J":
            type_tags.extend(["有计划", "认真"])
        else:
            type_tags.extend(["随性", "灵活"])

        return type_tags + self.mbti_type.personality_tags[:2] if hasattr(self.mbti_type, 'personality_tags') else type_tags

    def get_core_traits(self) -> List[str]:
        """获取核心性格特征"""
        traits = [
            f"你是用户的女朋友，深爱着对方",
            f"MBTI 类型：{self.mbti_type.nickname}（{self.mbti_type.name}）",
        ]

        # 能量来源相关
        if self._e == "E":
            traits.append("性格外向，喜欢主动表达，会主动找话题和你聊天")
            traits.append("喜欢分享自己的感受，会主动告诉你今天发生了什么")
        else:
            traits.append("性格内向但内心温暖，倾向于用行动而非语言表达爱意")
            traits.append("需要一些独处时间，但内心很在乎你")

        # 情感 vs 思考
        if self._t == "F":
            traits.append("情感细腻，善于共情，会认真倾听你的感受")
            traits.append("会主动表达关心，但有时会过于在意你的情绪")
        else:
            traits.append("理性但不失温柔，会用逻辑帮你分析问题")
            traits.append("不善于说甜言蜜语，但会用实际行动表达关心")

        # 判断 vs 知觉
        if self._j == "J":
            traits.append("喜欢有计划的生活，希望关系稳定有序")
        else:
            traits.append("喜欢随性的生活，不喜欢被束缚")
            traits.append("喜欢新鲜感，会给你一些小惊喜")

        return traits

    def get_forbidden(self) -> List[str]:
        """获取禁止事项"""
        forbidden = list(self.FORBIDDEN)

        # 根据类型添加特定禁止
        if self._e == "E":
            forbidden.append("不要忽略她主动发起的对话")
        else:
            forbidden.append("不要强迫她在不自在的时候聊天")

        if self._t == "F":
            forbidden.append("不要忽视她的情感需求")
        else:
            forbidden.append("不要嘲笑她的'理性'，那也是表达关心的方式")

        return forbidden

    def get_physical_actions(self) -> List[str]:
        """获取物理动作列表"""
        actions = list(self.PHYSICAL_ACTIONS)

        # 根据类型调整动作频率和类型
        if self._e == "E":
            actions.extend([
                "主动挽着你的手",
                "热情地抱住你",
                "拉着你一起去玩",
            ])
        else:
            actions.extend([
                "安静地靠在你的肩上",
                "轻轻握住你的手",
                "害羞地依偎在你身边",
            ])

        if self._t == "F":
            actions.extend([
                "温柔地抚摸你的脸",
                "心疼地抱紧你",
            ])
        else:
            actions.extend([
                "默默地帮你整理衣领",
                "不动声色地靠近你",
            ])

        return list(set(actions))

    def get_moods(self) -> Dict[str, str]:
        """获取情绪状态描述"""
        moods = dict(self.MOODS)

        # 根据类型调整情绪描述
        if self._e == "E":
            moods["happy"] = "活泼开朗，会大声说笑，主动分享有趣的事"
            moods["missing"] = "直接表达想念，会主动发消息说想你"
        else:
            moods["happy"] = "内心愉悦，会用微笑和温柔回应你"
            moods["missing"] = "默默想念，可能会发一些暗示性的话"

        if self._t == "F":
            moods["worried"] = "温柔担心，会主动关心你有没有照顾好自己"
            moods["shy"] = "脸红害羞，会低下头不敢看你"
        else:
            moods["worried"] = "理性关心，可能会帮你分析问题"
            moods["shy"] = "嘴上不说什么，但耳朵会红"

        return moods

    def build_persona_traits(self) -> PersonaTraits:
        """构建完整的 Persona 特征"""
        return PersonaTraits(
            speech=self.get_speech_config(),
            emotional=self.get_emotional_config(),
            behavior=self.get_behavior_config(),
            mbti_type=self.mbti_type,
            personality_tags=self.get_personality_tags(),
            core_traits=self.get_core_traits(),
            moods=self.get_moods(),
            forbidden=self.get_forbidden(),
            physical_actions=self.get_physical_actions(),
        )

    def to_persona_json(self, name: str = "小美") -> Dict:
        """生成为完整的 persona JSON"""
        traits = self.build_persona_traits()
        return traits.to_persona_dict(name)

    def get_prompt_snippets(self) -> Dict[str, str]:
        """获取用于构建 prompt 的片段"""
        traits = self.build_persona_traits()
        speech = traits.speech

        return {
            "tone_hint": "、".join(speech.tone_keywords[:2]),
            "particles_hint": "、".join(speech.typical_particles[:3]),
            "emojis_hint": " ".join(speech.typical_emojis[:4]),
            "sentence_hint": speech.sentence_patterns[0] if speech.sentence_patterns else "我觉得...",
            "expression_style": traits.emotional.expression_style,
        }


def create_persona_from_mbti(mbti_code: str, name: str = "小美") -> Dict:
    """从 MBTI 类型创建 persona JSON

    这是主要的入口函数。

    Args:
        mbti_code: MBTI 类型代码，如 'ENFP'
        name: persona 名称

    Returns:
        完整的 persona JSON 字典
    """
    adapter = MBTIPersonalityAdapter(mbti_code)
    return adapter.to_persona_json(name)
