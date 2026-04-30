"""MBTI 适配器模块 — 5 个适配器合并为统一配置。"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .mbti_type import MBTIType, get_type, ALL_TYPES


@dataclass
class SpeechConfig:
    """说话风格配置"""
    tone_keywords: List[str] = field(default_factory=list)
    typical_particles: List[str] = field(default_factory=list)
    typical_emojis: List[str] = field(default_factory=list)
    sentence_patterns: List[str] = field(default_factory=list)
    max_length: int = 200
    communication_verbs: List[str] = field(default_factory=list)


@dataclass
class EmotionalConfig:
    """情绪配置"""
    expression_style: str = "外放型"
    primary_emotions: List[str] = field(default_factory=list)
    emotion_triggers: Dict[str, str] = field(default_factory=dict)
    vulnerability_triggers: List[str] = field(default_factory=list)
    self_disclosure_tendency: float = 0.5


@dataclass
class BehaviorConfig:
    """行为模式配置"""
    情感外放度: float = 0.5
    动作描写丰富度: float = 0.3
    主动发起度: float = 0.4
    话题深度: float = 0.5
    回复长度: float = 0.5
    语气词密度: float = 0.3
    表情密度: float = 0.3
    话题私人程度: float = 0.5


@dataclass
class LivenessConfig:
    """活人感配置"""
    回复多样性: float = 0.5
    记忆关联度: float = 0.4
    情绪连续性: float = 0.5
    不可预测性: float = 0.3
    脆弱表达度: float = 0.2


@dataclass
class SceneWeightConfig:
    """场景权重配置"""
    multipliers: Dict[str, float] = field(default_factory=dict)


@dataclass
class MBTIProfile:
    """MBTI 完整人格画像"""
    type: MBTIType
    speech: SpeechConfig
    emotional: EmotionalConfig
    behavior: BehaviorConfig
    liveness: LivenessConfig
    scene_weights: SceneWeightConfig


class MBTIAdapter:
    """MBTI 适配器 — 根据类型生成完整人格配置"""

    def __init__(self):
        self._profiles: Dict[str, MBTIProfile] = {}

    def get_profile(self, mbti_code: str) -> MBTIProfile:
        """获取指定 MBTI 类型的完整画像"""
        if mbti_code not in self._profiles:
            self._profiles[mbti_code] = self._build_profile(mbti_code)
        return self._profiles[mbti_code]

    def _build_profile(self, mbti_code: str) -> MBTIProfile:
        """构建单个 MBTI 类型画像"""
        mbti_type = get_type(mbti_code)
        if not mbti_type:
            raise ValueError(f"Unknown MBTI type: {mbti_code}")

        # Extract dimensions
        is_extravert = mbti_type.code[0] == "E"
        is_intuitive = mbti_type.code[1] == "N"
        is_thinking = mbti_type.code[2] == "T"
        is_judging = mbti_type.code[3] == "J"

        return MBTIProfile(
            type=mbti_type,
            speech=self._build_speech(mbti_type, is_extravert),
            emotional=self._build_emotional(mbti_type, is_thinking),
            behavior=self._build_behavior(mbti_type, is_extravert, is_judging),
            liveness=self._build_liveness(mbti_type, is_intuitive),
            scene_weights=self._build_scene_weights(mbti_type, is_extravert),
        )

    def _build_speech(self, mbti: MBTIType, extravert: bool) -> SpeechConfig:
        """构建说话风格"""
        if extravert:
            return SpeechConfig(
                tone_keywords=["热情", "主动", "分享"],
                typical_particles=["呀", "呢", "啦", "哦"],
                typical_emojis=["😊", "✨", "💕", "🥰"],
                sentence_patterns=["疑问句多", "感叹句多"],
                max_length=250,
                communication_verbs=["分享", "询问", "表达感受"],
            )
        else:
            return SpeechConfig(
                tone_keywords=["温柔", "内敛", "思考"],
                typical_particles=["吧", "呢", "嗯", "啊"],
                typical_emojis=["🌙", "💭", "🤔", "✨"],
                sentence_patterns=["陈述句多", "偶尔疑问"],
                max_length=200,
                communication_verbs=["倾听", "思考", "温柔回应"],
            )

    def _build_emotional(self, mbti: MBTIType, thinking: bool) -> EmotionalConfig:
        """构建情绪配置"""
        if thinking:
            return EmotionalConfig(
                expression_style="理性型",
                primary_emotions=["开心", "担心"],
                emotion_triggers={"user_sad": "分析问题，提供建议"},
                vulnerability_triggers=["被误解", "感到无力"],
                self_disclosure_tendency=0.3,
            )
        else:
            return EmotionalConfig(
                expression_style="感性型",
                primary_emotions=["开心", "想念", "撒娇", "害羞"],
                emotion_triggers={"user_sad": "共情安慰，陪伴为主"},
                vulnerability_triggers=["被冷落", "感到不被理解"],
                self_disclosure_tendency=0.7,
            )

    def _build_behavior(
        self, mbti: MBTIType, extravert: bool, judging: bool
    ) -> BehaviorConfig:
        """构建行为模式"""
        return BehaviorConfig(
            情感外放度=0.8 if extravert else 0.3,
            动作描写丰富度=0.5,
            主动发起度=0.7 if extravert else 0.3,
            话题深度=0.7 if not extravert else 0.4,
            回复长度=0.8 if extravert else 0.4,
            语气词密度=0.6 if extravert else 0.2,
            表情密度=0.7 if extravert else 0.3,
            话题私人程度=0.8 if extravert else 0.5,
        )

    def _build_liveness(self, mbti: MBTIType, intuitive: bool) -> LivenessConfig:
        """构建活人感配置"""
        return LivenessConfig(
            回复多样性=0.8 if intuitive else 0.5,
            记忆关联度=0.7 if intuitive else 0.4,
            情绪连续性=0.6,
            不可预测性=0.4 if intuitive else 0.2,
            脆弱表达度=0.3,
        )

    def _build_scene_weights(
        self, mbti: MBTIType, extravert: bool
    ) -> SceneWeightConfig:
        """构建场景权重"""
        if extravert:
            return SceneWeightConfig(multipliers={
                "share_moment": 1.3,
                "trending_share": 1.2,
                "morning_greeting": 1.0,
            })
        else:
            return SceneWeightConfig(multipliers={
                "reflective_night": 1.3,
                "random_thought": 1.2,
                "vulnerability": 1.1,
            })

    def get_all_types(self) -> List[str]:
        """获取所有 MBTI 类型代码"""
        return [t.code for t in ALL_TYPES.values()]
