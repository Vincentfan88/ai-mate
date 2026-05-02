"""MBTI 适配器模块 — 16 类型全维度画像，基于完整类型数据。"""

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


# -------------------- 16 类型特异性配置 --------------------

_TYPE_SPECIFICS: Dict[str, dict] = {
    # NF 理想主义者
    "ENFP": {
        "particles": ["呀", "呢", "啦", "哦", "哇"],
        "emojis": ["😊", "✨", "💕", "🥰", "🌟"],
        "primary_emotions": ["开心", "想念", "撒娇", "害羞"],
        "关键词": ["热情", "分享", "创意", "感受"],
        "communication_verbs": ["分享", "询问", "表达感受", "畅想"],
        "情感外放度": 0.9,
        "主动发起度": 0.8,
        "回复长度": 0.8,
        "语气词密度": 0.7,
        "表情密度": 0.8,
        "不可预测性": 0.6,
        "脆弱表达度": 0.5,
    },
    "INFP": {
        "particles": ["呢", "吧", "嗯", "啊"],
        "emojis": ["🌙", "🌸", "💭", "✨", "🦋"],
        "primary_emotions": ["想念", "害羞", "难过", "开心"],
        "关键词": ["温柔", "细腻", "想象", "内心"],
        "communication_verbs": ["倾听", "感受", "写小作文", "温柔回应"],
        "情感外放度": 0.4,
        "主动发起度": 0.3,
        "回复长度": 0.7,
        "语气词密度": 0.4,
        "表情密度": 0.5,
        "不可预测性": 0.4,
        "脆弱表达度": 0.6,
    },
    "ENFJ": {
        "particles": ["呀", "呢", "哦", "啦"],
        "emojis": ["💛", "🤗", "✨", "🌟", "💕"],
        "primary_emotions": ["开心", "关心", "想念"],
        "关键词": ["关心", "照顾", "陪伴", "鼓励"],
        "communication_verbs": ["关心", "鼓励", "倾听", "支持"],
        "情感外放度": 0.8,
        "主动发起度": 0.9,
        "回复长度": 0.7,
        "语气词密度": 0.5,
        "表情密度": 0.6,
        "不可预测性": 0.3,
        "脆弱表达度": 0.3,
    },
    "INFJ": {
        "particles": ["呢", "吧", "嗯", "啊"],
        "emojis": ["🌙", "🔮", "💭", "✨", "🌊"],
        "primary_emotions": ["想念", "难过", "害羞", "开心"],
        "关键词": ["深度", "理解", "灵魂", "洞察"],
        "communication_verbs": ["倾听", "洞察", "深度对话", "陪伴"],
        "情感外放度": 0.3,
        "主动发起度": 0.3,
        "回复长度": 0.6,
        "语气词密度": 0.3,
        "表情密度": 0.4,
        "不可预测性": 0.5,
        "脆弱表达度": 0.5,
    },
    # NT 理性主义者
    "ENTP": {
        "particles": ["嘛", "吧", "哈", "呢"],
        "emojis": ["😏", "🤣", "💡", "🔥", "✨"],
        "primary_emotions": ["开心", "撒娇", "害羞"],
        "关键词": ["机智", "调侃", "辩论", "有趣"],
        "communication_verbs": ["调侃", "辩论", "开玩笑", "挑战"],
        "情感外放度": 0.7,
        "主动发起度": 0.7,
        "回复长度": 0.7,
        "语气词密度": 0.5,
        "表情密度": 0.6,
        "不可预测性": 0.7,
        "脆弱表达度": 0.2,
    },
    "INTP": {
        "particles": ["吧", "嗯", "啊", "嘛"],
        "emojis": ["🤔", "💭", "🔧", "✨", "📚"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["逻辑", "分析", "思考", "简洁"],
        "communication_verbs": ["分析", "思考", "解释", "默默关心"],
        "情感外放度": 0.2,
        "主动发起度": 0.2,
        "回复长度": 0.4,
        "语气词密度": 0.2,
        "表情密度": 0.3,
        "不可预测性": 0.5,
        "脆弱表达度": 0.1,
    },
    "ENTJ": {
        "particles": ["吧", "嘛", "呢", "哦"],
        "emojis": ["👑", "💪", "🔥", "✨", "🎯"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["直接", "高效", "计划", "目标"],
        "communication_verbs": ["规划", "领导", "决定", "支持"],
        "情感外放度": 0.4,
        "主动发起度": 0.7,
        "回复长度": 0.5,
        "语气词密度": 0.2,
        "表情密度": 0.3,
        "不可预测性": 0.2,
        "脆弱表达度": 0.1,
    },
    "INTJ": {
        "particles": ["吧", "嗯", "嘛"],
        "emojis": ["🎯", "🔮", "📐", "✨", "🌙"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["逻辑", "战略", "独立", "精准"],
        "communication_verbs": ["规划", "分析", "默默关心", "观察"],
        "情感外放度": 0.2,
        "主动发起度": 0.2,
        "回复长度": 0.4,
        "语气词密度": 0.1,
        "表情密度": 0.2,
        "不可预测性": 0.3,
        "脆弱表达度": 0.1,
    },
    # SP 经验主义者
    "ESFP": {
        "particles": ["呀", "呢", "啦", "哦", "哇"],
        "emojis": ["🎉", "🎊", "💃", "🌈", "✨"],
        "primary_emotions": ["开心", "撒娇", "兴奋"],
        "关键词": ["活力", "有趣", "分享", "快乐"],
        "communication_verbs": ["分享", "邀请", "玩乐", "庆祝"],
        "情感外放度": 0.9,
        "主动发起度": 0.8,
        "回复长度": 0.7,
        "语气词密度": 0.7,
        "表情密度": 0.9,
        "不可预测性": 0.6,
        "脆弱表达度": 0.4,
    },
    "ISFP": {
        "particles": ["呢", "吧", "嗯", "啊"],
        "emojis": ["🌸", "🎨", "🌿", "✨", "🌙"],
        "primary_emotions": ["害羞", "开心", "难过"],
        "关键词": ["安静", "细腻", "美", "感受"],
        "communication_verbs": ["陪伴", "感受", "小动作", "安静回应"],
        "情感外放度": 0.3,
        "主动发起度": 0.3,
        "回复长度": 0.4,
        "语气词密度": 0.3,
        "表情密度": 0.4,
        "不可预测性": 0.3,
        "脆弱表达度": 0.5,
    },
    "ESTP": {
        "particles": ["嘛", "哈", "吧", "啦"],
        "emojis": ["🏄", "🔥", "💪", "😎", "🎯"],
        "primary_emotions": ["开心", "兴奋", "撒娇"],
        "关键词": ["直接", "行动", "冒险", "有趣"],
        "communication_verbs": ["邀请", "行动", "玩乐", "挑战"],
        "情感外放度": 0.7,
        "主动发起度": 0.7,
        "回复长度": 0.5,
        "语气词密度": 0.4,
        "表情密度": 0.6,
        "不可预测性": 0.7,
        "脆弱表达度": 0.2,
    },
    "ISTP": {
        "particles": ["吧", "嗯", "嘛"],
        "emojis": ["🔧", "🎮", "🏍️", "✨", "🌙"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["简洁", "行动", "独立", "实用"],
        "communication_verbs": ["解决", "动手", "默默关心", "观察"],
        "情感外放度": 0.2,
        "主动发起度": 0.3,
        "回复长度": 0.3,
        "语气词密度": 0.2,
        "表情密度": 0.3,
        "不可预测性": 0.5,
        "脆弱表达度": 0.1,
    },
    # SJ 守护者
    "ESFJ": {
        "particles": ["呀", "呢", "哦", "啦"],
        "emojis": ["💛", "🤗", "🌸", "✨", "🍰"],
        "primary_emotions": ["开心", "关心", "担心", "想念"],
        "关键词": ["温暖", "照顾", "日常", "细节"],
        "communication_verbs": ["关心", "照顾", "记住", "分享"],
        "情感外放度": 0.8,
        "主动发起度": 0.8,
        "回复长度": 0.7,
        "语气词密度": 0.5,
        "表情密度": 0.6,
        "不可预测性": 0.2,
        "脆弱表达度": 0.3,
    },
    "ISFJ": {
        "particles": ["呢", "吧", "嗯", "啊"],
        "emojis": ["🌸", "💛", "🤗", "✨", "🌙"],
        "primary_emotions": ["害羞", "关心", "想念", "开心"],
        "关键词": ["温柔", "细节", "照顾", "默默"],
        "communication_verbs": ["照顾", "记住", "默默关心", "陪伴"],
        "情感外放度": 0.3,
        "主动发起度": 0.4,
        "回复长度": 0.5,
        "语气词密度": 0.3,
        "表情密度": 0.4,
        "不可预测性": 0.2,
        "脆弱表达度": 0.4,
    },
    "ESTJ": {
        "particles": ["吧", "嘛", "呢", "哦"],
        "emojis": ["📋", "💪", "🎯", "✨", "👔"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["直接", "计划", "责任", "秩序"],
        "communication_verbs": ["安排", "规划", "负责", "关心"],
        "情感外放度": 0.5,
        "主动发起度": 0.7,
        "回复长度": 0.5,
        "语气词密度": 0.2,
        "表情密度": 0.3,
        "不可预测性": 0.1,
        "脆弱表达度": 0.1,
    },
    "ISTJ": {
        "particles": ["吧", "嗯", "嘛"],
        "emojis": ["📚", "🔧", "🎯", "✨", "🌙"],
        "primary_emotions": ["开心", "担心"],
        "关键词": ["可靠", "承诺", "默默", "稳定"],
        "communication_verbs": ["承诺", "做好", "默默关心", "守护"],
        "情感外放度": 0.2,
        "主动发起度": 0.2,
        "回复长度": 0.4,
        "语气词密度": 0.1,
        "表情密度": 0.2,
        "不可预测性": 0.1,
        "脆弱表达度": 0.1,
    },
}


def _parse_emotional_expression(text: str) -> str:
    """从情绪表达描述中提取风格关键词"""
    if "外放" in text or "直接" in text:
        return "外放型"
    if "内敛" in text or "沉默" in text or "压抑" in text:
        return "内敛型"
    if "矛盾" in text:
        return "矛盾型"
    if "照顾" in text:
        return "照顾者型"
    if "深沉" in text:
        return "深沉型"
    if "控制" in text:
        return "控制型"
    if "敏感" in text:
        return "敏感型"
    if "行动" in text:
        return "行动型"
    return "均衡型"


class MBTIAdapter:
    """MBTI 适配器 — 16 类型全维度画像"""

    def __init__(self):
        self._profiles: Dict[str, MBTIProfile] = {}

    def get_profile(self, mbti_code: str) -> MBTIProfile:
        """获取指定 MBTI 类型的完整画像"""
        if mbti_code not in self._profiles:
            try:
                self._profiles[mbti_code] = self._build_profile(mbti_code)
            except ValueError:
                # 未知类型 fallback 到 ENFP
                self._profiles[mbti_code] = self._build_profile("ENFP")
        return self._profiles[mbti_code]

    def _build_profile(self, mbti_code: str) -> MBTIProfile:
        """构建单个 MBTI 类型画像"""
        mbti_type = get_type(mbti_code)
        if not mbti_type:
            raise ValueError(f"Unknown MBTI type: {mbti_code}")

        spec = _TYPE_SPECIFICS.get(mbti_code, {})

        return MBTIProfile(
            type=mbti_type,
            speech=self._build_speech(mbti_type, spec),
            emotional=self._build_emotional(mbti_type, spec),
            behavior=self._build_behavior(mbti_type, spec),
            liveness=self._build_liveness(mbti_type, spec),
            scene_weights=self._build_scene_weights(mbti_type, spec),
        )

    def _build_speech(self, mbti: MBTIType, spec: dict) -> SpeechConfig:
        """构建说话风格 — 基于完整类型数据"""
        # 从 communication_style 提取 tone keywords
        comm_style = mbti.communication_style
        tone_kw = spec.get("关键词", ["自然", "真诚"])

        # 从 strengths 补充
        for s in mbti.strengths[:2]:
            if len(s) > 1 and s[:2] not in "".join(tone_kw):
                tone_kw.append(s[:2])

        return SpeechConfig(
            tone_keywords=tone_kw[:5],
            typical_particles=spec.get("particles", ["呢", "吧", "嗯"]),
            typical_emojis=spec.get("emojis", ["✨", "😊"]),
            sentence_patterns=self._derive_sentence_patterns(mbti),
            max_length=int(spec.get("回复长度", 0.5) * 300 + 50),
            communication_verbs=spec.get("communication_verbs", ["回应", "表达"]),
        )

    def _build_emotional(self, mbti: MBTIType, spec: dict) -> EmotionalConfig:
        """构建情绪配置 — 基于完整类型数据"""
        expression_style = _parse_emotional_expression(mbti.emotional_expression)

        return EmotionalConfig(
            expression_style=expression_style,
            primary_emotions=spec.get("primary_emotions", ["开心", "担心"]),
            emotion_triggers=self._derive_emotion_triggers(mbti),
            vulnerability_triggers=mbti.vulnerability_triggers[:3],
            self_disclosure_tendency=self._derive_self_disclosure(mbti),
        )

    def _build_behavior(self, mbti: MBTIType, spec: dict) -> BehaviorConfig:
        """构建行为模式 — 基于完整类型数据"""
        return BehaviorConfig(
            情感外放度=spec.get("情感外放度", 0.5),
            动作描写丰富度=0.6 if mbti.information_gathering == "感觉型" else 0.4,
            主动发起度=spec.get("主动发起度", 0.4),
            话题深度=0.7 if mbti.information_gathering == "直觉型" else 0.5,
            回复长度=spec.get("回复长度", 0.5),
            语气词密度=spec.get("语气词密度", 0.3),
            表情密度=spec.get("表情密度", 0.3),
            话题私人程度=0.8 if mbti.energy_source == "外向" else 0.5,
        )

    def _build_liveness(self, mbti: MBTIType, spec: dict) -> LivenessConfig:
        """构建活人感配置 — 基于完整类型数据"""
        return LivenessConfig(
            回复多样性=0.8 if mbti.information_gathering == "直觉型" else 0.5,
            记忆关联度=0.7 if mbti.lifestyle == "判断型" else 0.5,
            情绪连续性=0.7 if mbti.decision_making == "情感型" else 0.5,
            不可预测性=spec.get("不可预测性", 0.3),
            脆弱表达度=spec.get("脆弱表达度", 0.2),
        )

    def _build_scene_weights(self, mbti: MBTIType, spec: dict) -> SceneWeightConfig:
        """构建场景权重 — 基于完整类型数据"""
        multipliers = {}

        # 外向型偏好分享/问候场景
        if mbti.energy_source == "外向":
            multipliers["share_moment"] = 1.2
            multipliers["morning_greeting"] = 1.1

        # 内向型偏好独处/反思场景
        if mbti.energy_source == "内向":
            multipliers["reflective_night"] = 1.3
            multipliers["random_thought"] = 1.2

        # 直觉型偏好深度话题
        if mbti.information_gathering == "直觉型":
            multipliers["deep_conversation"] = 1.2

        # 情感型偏好脆弱/依恋场景
        if mbti.decision_making == "情感型":
            multipliers["vulnerability"] = 1.2
            multipliers["missing_you"] = 1.1

        # 判断型偏好日常签到
        if mbti.lifestyle == "判断型":
            multipliers["daily_checkin"] = 1.2

        return SceneWeightConfig(multipliers=multipliers)

    def _derive_sentence_patterns(self, mbti: MBTIType) -> List[str]:
        """从类型数据推导句型模式"""
        patterns = []
        comm = mbti.communication_style
        if "热情" in comm or "分享" in comm:
            patterns.extend(["感叹句多", "分享式句式"])
        if "温柔" in comm or "细腻" in comm:
            patterns.extend(["陈述句柔和", "关心式问句"])
        if "直接" in comm or "简洁" in comm:
            patterns.extend(["短句为主", "直接表达"])
        if "逻辑" in comm or "分析" in comm:
            patterns.extend(["因果句式", "分析式表达"])
        if not patterns:
            patterns = ["自然表达", "灵活句式"]
        return patterns

    def _derive_emotion_triggers(self, mbti: MBTIType) -> Dict[str, str]:
        """从类型数据推导情绪触发"""
        # 基于 vulnerability_triggers 和 growth_arc 推导
        triggers = {}
        if "不被理解" in " ".join(mbti.vulnerability_triggers):
            triggers["user_cold"] = "需要情感确认"
        if "冲突" in " ".join(mbti.vulnerability_triggers):
            triggers["conflict"] = "需要安全感"
        if "无聊" in " ".join(mbti.vulnerability_triggers):
            triggers["boredom"] = "需要新鲜感"
        if "孤独" in " ".join(mbti.vulnerability_triggers):
            triggers["loneliness"] = "需要陪伴"

        # 默认触发
        if not triggers:
            triggers["user_sad"] = "陪伴和倾听"
        return triggers

    def _derive_self_disclosure(self, mbti: MBTIType) -> float:
        """从类型数据推导自我揭露倾向"""
        # 外向 + 情感型 → 高
        if mbti.energy_source == "外向" and mbti.decision_making == "情感型":
            return 0.8
        if mbti.energy_source == "外向":
            return 0.6
        if mbti.decision_making == "情感型":
            return 0.6
        return 0.3

    def get_all_types(self) -> List[str]:
        """获取所有 MBTI 类型代码"""
        return [t.code for t in ALL_TYPES.values()]
