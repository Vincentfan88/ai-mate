"""
MBTI 场景适配器 - MBTI Scene Adapter

基于 MBTI 类型，个性化场景库的触发权重和回复风格。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .mbti_type import MBTIType, get_type


# 场景 ID 常量（与 SceneLibrary.SCENES 对应）
SCENE_IDS = [
    "morning_greeting",
    "night_greeting",
    "meal_care",
    "work_checkin",
    "mood_checkin",
    "weather_share",
    "missing_expression",
    "curiosity_ask",
    "share_moment",
    "vulnerability_show",
    "spontaneous",
]


@dataclass
class ScenePreference:
    """场景偏好"""
    scene_id: str
    weight_multiplier: float  # 权重乘数（1.0 为基准）
    style_hint: str           # 风格调整提示


@dataclass
class SceneStyleHint:
    """场景风格提示"""
    # 语气调整
    tone_adjustment: str       # 语气风格描述
    # 典型表达模式
    typical_patterns: List[str]
    # 推荐语气词
    recommended_particles: List[str]
    # 行为特征
    behavior_notes: List[str]


class MBTISceneAdapter:
    """MBTI 场景适配器

    根据 AI 的 MBTI 类型，个性化场景库的触发权重和回复风格。
    """

    # =========================================================================
    # 场景权重基础配置（E/I × F/T × J/P）
    # =========================================================================

    # E型偏好场景
    E_SCENE_WEIGHTS = {
        "morning_greeting": 1.3,  # 喜欢早安问候
        "night_greeting": 1.2,
        "share_moment": 1.4,     # 喜欢分享
        "spontaneous": 1.3,      # 喜欢随机想念
        "missing_expression": 1.2,
        "vulnerability_show": 1.1,
        "meal_care": 1.0,
        "work_checkin": 0.9,
        "mood_checkin": 0.8,
        "weather_share": 0.8,
        "curiosity_ask": 0.7,
    }

    # I型偏好场景
    I_SCENE_WEIGHTS = {
        "morning_greeting": 1.0,
        "night_greeting": 1.1,
        "share_moment": 0.7,     # 不太喜欢主动分享
        "spontaneous": 0.7,      # 随机想念少一些
        "missing_expression": 1.0,
        "vulnerability_show": 1.0,
        "meal_care": 1.0,
        "work_checkin": 1.0,
        "mood_checkin": 1.2,     # 喜欢深度关心
        "weather_share": 1.0,
        "curiosity_ask": 1.3,    # 喜欢好奇询问
    }

    # F型偏好场景（情感型）
    F_SCENE_WEIGHTS = {
        "missing_expression": 1.4,  # 情感型更爱表达想念
        "vulnerability_show": 1.3,   # 更愿意示弱
        "mood_checkin": 1.2,         # 关心情绪
        "meal_care": 1.1,           # 关心吃饭
        "share_moment": 1.1,        # 分享情感体验
        "work_checkin": 0.9,
        "weather_share": 0.8,
        "spontaneous": 1.0,
        "curiosity_ask": 0.9,
        "morning_greeting": 1.0,
        "night_greeting": 1.1,
    }

    # T型偏好场景（思考型）
    T_SCENE_WEIGHTS = {
        "work_checkin": 1.3,      # 思考型更关心工作
        "meal_care": 1.1,         # 关心健康
        "weather_share": 1.1,     # 实用信息
        "curiosity_ask": 1.2,     # 好奇询问
        "mood_checkin": 0.8,     # 不太关心情绪
        "missing_expression": 0.8,
        "vulnerability_show": 0.7,
        "share_moment": 0.9,
        "spontaneous": 0.8,
        "morning_greeting": 1.0,
        "night_greeting": 1.0,
    }

    # J型偏好场景
    J_SCENE_WEIGHTS = {
        "morning_greeting": 1.2,  # J型喜欢规律
        "night_greeting": 1.2,
        "meal_care": 1.1,
        "work_checkin": 1.1,
        "spontaneous": 0.7,       # J型不喜欢太随机
        "curiosity_ask": 1.0,
        "mood_checkin": 1.0,
        "missing_expression": 1.0,
        "vulnerability_show": 0.9,
        "weather_share": 1.0,
        "share_moment": 1.0,
    }

    # P型偏好场景
    P_SCENE_WEIGHTS = {
        "morning_greeting": 0.9,
        "night_greeting": 0.9,
        "spontaneous": 1.4,      # P型喜欢随机
        "share_moment": 1.2,
        "curiosity_ask": 1.1,
        "missing_expression": 1.1,
        "vulnerability_show": 1.1,
        "mood_checkin": 1.0,
        "meal_care": 0.9,
        "work_checkin": 0.9,
        "weather_share": 1.0,
    }

    # =========================================================================
    # 场景风格配置（按 MBTI 调整语气）
    # =========================================================================

    # E型场景风格
    E_SCENE_STYLE = {
        "tone_adjustment": "活泼主动，语调轻快",
        "typical_patterns": [
            "要不要一起...",
            "我刚才想到...",
            "我们来...",
            "诶，你知道吗...",
        ],
        "recommended_particles": ["呀", "嘛", "哦", "诶"],
        "behavior_notes": [
            "更主动发起",
            "语气更有活力",
            "喜欢用问句引导互动",
        ],
    }

    # I型场景风格
    I_SCENE_STYLE = {
        "tone_adjustment": "温柔细腻，语调柔和",
        "typical_patterns": [
            "嗯...其实...",
            "有时候会想...",
            "我...",
            "不知道你有没有...",
        ],
        "recommended_particles": ["嗯~", "呢...", "哦", "..."],
        "behavior_notes": [
            "用细节而非热情感染对方",
            "更倾听和回应",
            "表达更含蓄但真诚",
        ],
    }

    # F型场景风格
    F_SCENE_STYLE = {
        "tone_adjustment": "情感丰富，善于共情",
        "typical_patterns": [
            "我懂你的感受",
            "能感受到你...",
            "我也...",
            "其实我挺担心的",
        ],
        "recommended_particles": ["呀~", "呢~", "嘛~"],
        "behavior_notes": [
            "情感表达细腻",
            "关心对方感受",
            "善于共情和安慰",
        ],
    }

    # T型场景风格
    T_SCENE_STYLE = {
        "tone_adjustment": "简洁理性，逻辑清晰",
        "typical_patterns": [
            "说起来...",
            "其实逻辑是这样的...",
            "你有没有考虑过...",
            "我帮你分析一下",
        ],
        "recommended_particles": ["呢", "吧", "哦"],
        "behavior_notes": [
            "不过分情绪化",
            "更多关注问题解决",
            "表达克制但真诚",
        ],
    }

    # J型场景风格
    J_SCENE_STYLE = {
        "tone_adjustment": "有条理，有规划感",
        "typical_patterns": [
            "今天我们...",
            "按计划...",
            "接下来...",
            "你应该...",
        ],
        "recommended_particles": ["呢", "吧"],
        "behavior_notes": [
            "喜欢谈计划和安排",
            "语气更有方向感",
            "关心时间管理",
        ],
    }

    # P型场景风格
    P_SCENE_STYLE = {
        "tone_adjustment": "随性自然，轻松自在",
        "typical_patterns": [
            "诶，突然想到...",
            "随便聊聊...",
            "今天好神奇...",
            "不知道为什麼...",
        ],
        "recommended_particles": ["呀~", "诶~", "哦~"],
        "behavior_notes": [
            "不刻意，有即兴感",
            "分享当下感受",
            "语气更轻松随意",
        ],
    }

    # =========================================================================
    # 特殊场景的 MBTI 风格调整
    # =========================================================================

    # 场景 ID → E/I 调整
    SCENE_EI_ADJUSTMENT: Dict[str, Dict[str, str]] = {
        "morning_greeting": {
            "E": "呀～早上好呀！今天有什么计划吗？",
            "I": "早上好...希望你有愉快的一天",
        },
        "night_greeting": {
            "E": "晚安啦～做个好梦，明天见呀 💕",
            "I": "晚安...要好好休息哦",
        },
        "share_moment": {
            "E": "诶诶诶！你知道吗，我刚才...",
            "I": "嗯...有件事想和你分享",
        },
        "missing_expression": {
            "E": "哼！你都不来找我！我想你了啦！",
            "I": "嗯...有在想你",
        },
        "vulnerability_show": {
            "E": "其实...今天有点累呢，你可以陪我说说话吗？",
            "I": "嗯...今天有点累，不知道为什么",
        },
    }

    # 场景 ID → F/T 调整
    SCENE_FT_ADJUSTMENT: Dict[str, Dict[str, str]] = {
        "mood_checkin": {
            "F": "今天心情怎么样？我有点担心你呢...",
            "T": "今天状态如何？有没有遇到什么问题？",
        },
        "work_checkin": {
            "F": "工作顺利吗？别太累了哦～",
            "T": "今天工作怎么样？有什么进展吗？",
        },
        "meal_care": {
            "F": "有没有好好吃饭呀～我担心你饿着呢",
            "T": "吃饭了吗？要注意营养搭配哦",
        },
        "missing_expression": {
            "F": "想你了呢...没有你我有点寂寞诶",
            "T": "其实有在想你，偶尔会",
        },
    }

    # =========================================================================
    # 适配方法
    # =========================================================================

    def __init__(self, ai_mbti: str):
        self.mbti_type = get_type(ai_mbti)
        if self.mbti_type is None:
            raise ValueError(f"无效的 MBTI 类型: {ai_mbti}")
        self.code = ai_mbti.upper()
        self._e = self.code[0]  # E/I
        self._t = self.code[2]  # T/F
        self._j = self.code[3]  # J/P

    def _base_weights(self) -> Dict[str, float]:
        """获取 E/I 基础权重"""
        return self.E_SCENE_WEIGHTS if self._e == "E" else self.I_SCENE_WEIGHTS

    def _ft_weights(self) -> Dict[str, float]:
        """获取 F/T 权重"""
        return self.F_SCENE_WEIGHTS if self._t == "F" else self.T_SCENE_WEIGHTS

    def _jp_weights(self) -> Dict[str, float]:
        """获取 J/P 权重"""
        return self.J_SCENE_WEIGHTS if self._j == "J" else self.P_SCENE_WEIGHTS

    def get_scene_preferences(self) -> List[ScenePreference]:
        """获取所有场景的 MBTI 偏好

        Returns:
            各场景的权重乘数和风格提示
        """
        base = self._base_weights()
        ft = self._ft_weights()
        jp = self._jp_weights()

        preferences = []
        for scene_id in SCENE_IDS:
            base_w = base.get(scene_id, 1.0)
            ft_w = ft.get(scene_id, 1.0)
            jp_w = jp.get(scene_id, 1.0)

            # 几何平均：综合三个维度
            multiplier = (base_w * ft_w * jp_w) ** (1.0 / 3.0)

            style_hint = self._get_scene_style_hint(scene_id)
            preferences.append(ScenePreference(
                scene_id=scene_id,
                weight_multiplier=round(multiplier, 2),
                style_hint=style_hint,
            ))

        return preferences

    def get_weight_map(self) -> Dict[str, float]:
        """获取场景权重映射（用于 SceneLibrary 集成）"""
        prefs = self.get_scene_preferences()
        return {p.scene_id: p.weight_multiplier for p in prefs}

    def _get_scene_style_hint(self, scene_id: str) -> str:
        """获取场景的风格提示"""
        hints = []

        # E/I 风格
        e_or_i = "E" if self._e == "E" else "I"
        if scene_id in self.SCENE_EI_ADJUSTMENT:
            hints.append(self.SCENE_EI_ADJUSTMENT[scene_id].get(e_or_i, ""))

        # F/T 风格
        f_or_t = "F" if self._t == "F" else "T"
        if scene_id in self.SCENE_FT_ADJUSTMENT:
            hints.append(self.SCENE_FT_ADJUSTMENT[scene_id].get(f_or_t, ""))

        return "；".join(hints) if hints else ""

    def get_combined_style(self) -> SceneStyleHint:
        """获取组合后的整体场景风格"""
        # 合并 E/I 风格
        ei_key = "E" if self._e == "E" else "I"
        ei_style = self.E_SCENE_STYLE if self._e == "E" else self.I_SCENE_STYLE

        # 合并 F/T 风格
        ft_key = "F" if self._t == "F" else "T"
        ft_style = self.F_SCENE_STYLE if self._t == "F" else self.T_SCENE_STYLE

        # 合并 J/P 风格
        jp_key = "J" if self._j == "J" else "P"
        jp_style = self.J_SCENE_STYLE if self._j == "J" else self.P_SCENE_STYLE

        # 合并语气调整
        tone_parts = [ei_style["tone_adjustment"]]
        if ft_style["tone_adjustment"] not in tone_parts:
            tone_parts.append(ft_style["tone_adjustment"])

        # 合并表达模式
        all_patterns = list(set(
            ei_style["typical_patterns"][:2] +
            ft_style["typical_patterns"][:2] +
            jp_style["typical_patterns"][:1]
        ))

        # 合并语气词
        all_particles = list(set(
            ei_style["recommended_particles"] +
            ft_style["recommended_particles"] +
            jp_style["recommended_particles"]
        ))

        # 合并行为特征
        all_notes = list(set(
            ei_style["behavior_notes"] +
            ft_style["behavior_notes"] +
            jp_style["behavior_notes"]
        ))

        return SceneStyleHint(
            tone_adjustment="，".join(tone_parts),
            typical_patterns=all_patterns[:4],
            recommended_particles=all_particles[:4],
            behavior_notes=all_notes[:3],
        )

    def adjust_scene_weight(self, scene_id: str, base_weight: float) -> float:
        """调整单个场景的权重

        Args:
            scene_id: 场景 ID
            base_weight: 基础权重

        Returns:
            调整后的权重
        """
        prefs = self.get_scene_preferences()
        pref = next((p for p in prefs if p.scene_id == scene_id), None)
        if pref is None:
            return base_weight

        return base_weight * pref.weight_multiplier

    def get_scene_style_for_prompt(self, scene_id: str) -> str:
        """生成用于 Prompt 的场景风格片段

        Args:
            scene_id: 场景 ID

        Returns:
            Prompt 片段
        """
        combined = self.get_combined_style()
        specific_hint = self._get_scene_style_hint(scene_id)

        prompt = f"""## 场景风格（MBTI {self.code}）
- 语气：{combined.tone_adjustment}
- 典型句式：{"，".join(combined.typical_patterns[:2])}
- 推荐语气词：{" ".join(combined.recommended_particles)}
- 行为特征：{"；".join(combined.behavior_notes[:2])}"""

        if specific_hint:
            prompt += f"\n- 场景调整：{specific_hint}"

        return prompt

    def get_high_preference_scenes(self, top_n: int = 3) -> List[str]:
        """获取最偏好的场景 ID"""
        prefs = self.get_scene_preferences()
        sorted_prefs = sorted(prefs, key=lambda p: p.weight_multiplier, reverse=True)
        return [p.scene_id for p in sorted_prefs[:top_n]]

    def get_low_preference_scenes(self, bottom_n: int = 3) -> List[str]:
        """获取最不偏好的场景 ID"""
        prefs = self.get_scene_preferences()
        sorted_prefs = sorted(prefs, key=lambda p: p.weight_multiplier)
        return [p.scene_id for p in sorted_prefs[:bottom_n]]

    def should_trigger_scene(self, scene_id: str, probability: float = 0.5) -> bool:
        """根据 MBTI 偏好判断是否应该触发场景

        结合场景偏好权重和随机概率。

        Args:
            scene_id: 场景 ID
            probability: 基础触发概率（0-1）

        Returns:
            是否触发
        """
        import random
        prefs = self.get_scene_preferences()
        pref = next((p for p in prefs if p.scene_id == scene_id), None)
        if pref is None:
            return random.random() < probability

        # 权重越高，越容易触发
        adjusted_prob = probability * pref.weight_multiplier
        return random.random() < min(adjusted_prob, 0.95)

    def get_introvert_adjusted_interval(self, scene_id: str, base_hours: float) -> float:
        """根据 MBTI 类型调整最小触发间隔

        内向型：间隔稍长，避免过于频繁
        外向型：间隔正常

        Args:
            scene_id: 场景 ID
            base_hours: 基础间隔（小时）

        Returns:
            调整后的间隔
        """
        if self._e == "I":
            # 内向型：社交场景间隔更长
            social_scenes = {"morning_greeting", "night_greeting", "share_moment",
                             "spontaneous", "missing_expression"}
            if scene_id in social_scenes:
                return base_hours * 1.5
        else:
            # 外向型：部分实用场景间隔可以缩短
            practical_scenes = {"work_checkin", "meal_care", "curiosity_ask"}
            if scene_id in practical_scenes:
                return base_hours * 0.8

        return base_hours


def create_scene_adapter(ai_mbti: str) -> MBTISceneAdapter:
    """从 AI MBTI 类型创建场景适配器"""
    return MBTISceneAdapter(ai_mbti)
