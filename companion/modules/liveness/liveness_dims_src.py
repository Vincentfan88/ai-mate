"""
活人感八维度整合系统 - Liveness Dimensions Integration

整合身体存在感、不可预测性、一致性、情绪化、脆弱性、成长性、依恋度。
"""

from typing import Dict, List, Optional
from datetime import datetime


class LivenessDimensions:
    """活人感八维度整合"""

    def __init__(self, user_profile=None, attachment=None):
        """
        Args:
            user_profile: UserProfile 实例（来自 SharedState，避免创建隔离实例）
            attachment: AttachmentSystem 实例（可选）
        """
        self._physical = None
        self._unpredictable = None
        self._consistency = None
        self._emotional_memory = None
        self._vulnerability = None
        self._attachment = attachment

        # 外部传入的 user_profile（避免隔离实例问题）
        self._user_profile_external = user_profile
        self._user_profile = None  # 仅作兜底

        self.missing_level = 0.5
        self.current_mood_label = "舒适"

    def _get_physical(self):
        if self._physical is None:
            from core.filters.physical_presence import PhysicalPresenceSystem
            self._physical = PhysicalPresenceSystem()
        return self._physical

    def _get_unpredictable(self):
        if self._unpredictable is None:
            from core.engine.unpredictability import UnpredictabilitySystem
            self._unpredictable = UnpredictabilitySystem()
        return self._unpredictable

    def _get_consistency(self):
        if self._consistency is None:
            from core.services.consistency import ConsistencySystem
            self._consistency = ConsistencySystem()
        return self._consistency

    def _get_emotional_memory(self):
        if self._emotional_memory is None:
            from core.services.emotional_memory import EmotionalMemory
            self._emotional_memory = EmotionalMemory()
        return self._emotional_memory

    def _get_vulnerability(self):
        if self._vulnerability is None:
            from core.filters.vulnerability import VulnerabilitySystem
            self._vulnerability = VulnerabilitySystem()
        return self._vulnerability

    def _get_user_profile(self):
        """获取 UserProfile 实例（优先使用外部传入的，否则兜底创建）"""
        if self._user_profile_external is not None:
            return self._user_profile_external
        if self._user_profile is None:
            from core.stores.profile import UserProfile
            self._user_profile = UserProfile()
        return self._user_profile

    def _get_attachment(self):
        if self._attachment is None:
            from core.attachment import AttachmentSystem
            self._attachment = AttachmentSystem()
        return self._attachment

    def update_context(self, missing_level: float = None, mood_label: str = None):
        """更新上下文状态"""
        if missing_level is not None:
            self.missing_level = missing_level
        if mood_label is not None:
            self.current_mood_label = mood_label

    def build_full_prompt(self, include_all: bool = True) -> str:
        """构建完整的活人感 Prompt"""
        prompts = []

        # 1. 身体存在感
        prompts.append(self._get_physical().build_physical_prompt())

        # 2. 不可预测性
        if include_all and self._get_unpredictable().should_trigger_surprise():
            surprise = self._get_unpredictable().generate_surprise()
            if surprise:
                prompts.append(f"\n## 意外时刻\n{surprise['content']}\n")

        # 3. 一致性
        prompts.append(self._get_consistency().build_consistency_prompt())

        # 4. 情绪记忆
        prompts.append(self._get_emotional_memory().build_emotional_prompt())

        # 5. 脆弱性
        prompts.append(self._get_vulnerability().build_vulnerability_prompt(
            include_vulnerability=True
        ))

        # 6. 成长性
        prompts.append(self._get_user_profile().build_growth_prompt())

        # 7. 依恋度
        prompts.append(self._get_attachment().build_attachment_prompt(self.missing_level))

        return "\n".join(prompts)

    def build_chat_prompt(self) -> str:
        """构建聊天场景的 Prompt"""
        return self.build_full_prompt(include_all=True)

    def build_proactive_prompt(self, scene_type: str = None) -> str:
        """构建主动发消息场景的 Prompt"""
        prompts = []

        # 身体存在感 - 主动场景需要更强的存在感
        prompts.append(self._get_physical().build_physical_prompt())

        # 不可预测性
        prompts.append(self._get_unpredictable().build_unpredictable_prompt())

        # 情绪记忆
        prompts.append(self._get_emotional_memory().build_emotional_prompt())

        # 脆弱性
        prompts.append(self._get_vulnerability().build_vulnerability_prompt(
            include_vulnerability=True
        ))

        # 成长性
        prompts.append(self._get_user_profile().build_growth_prompt())

        # 依恋度
        prompts.append(self._get_attachment().build_attachment_prompt(self.missing_level))

        return "\n".join(prompts)

    def record_interaction(self, user_message: str, ai_response: str, mood_value: float = None):
        """记录一次交互"""
        # 学习用户偏好
        self._get_consistency().learn_from_interaction(user_message, ai_response)

        # 记录情绪
        if mood_value is not None:
            mood_label = self._value_to_label(mood_value)
            self._get_emotional_memory().record_mood(
                mood_value=mood_value,
                mood_label=mood_label,
                reason=user_message[:50] if user_message else "一般对话"
            )

        # 更新亲密度（基于积极互动）
        if any(word in ai_response.lower() for word in ["喜欢", "爱你", "想你", "抱抱"]):
            self._get_attachment().update_intimacy(0.005)
            self._get_user_profile().update_intimacy(0.003)

    def get_all_stats(self) -> Dict:
        """获取所有维度的统计"""
        return {
            "physical": {
                "current_time": self._get_physical().get_time_context().get("description", ""),
                "current_weather": self._get_physical().get_weather_context().get("weather", "")
            },
            "unpredictability": {
                "has_surprises": self._get_unpredictable().last_surprise_time is not None
            },
            "emotional": self._get_emotional_memory().get_mood_streak(),
            "vulnerability": self._get_vulnerability().get_vulnerability_stats(),
            "growth": {
                "intimacy": self._get_user_profile().intimacy_level,
                "trust": self._get_user_profile().trust_level,
                "stage": self._get_user_profile().get_stage_name(),
                "duration": self._get_user_profile().get_relationship_duration()["formatted"]
            },
            "attachment": self._get_attachment().get_intimacy_stats()
        }

    def get_liveness_score(self) -> Dict[str, float]:
        """计算各维度活人感得分"""
        return {
            "主动性": 0.85,  # 调度器已实现
            "一致性": self._calculate_consistency_score(),
            "成长性": self._calculate_growth_score(),
            "情绪化": self._calculate_emotional_score(),
            "脆弱性": self._calculate_vulnerability_score(),
            "身体存在感": self._calculate_physical_score(),
            "不可预测性": self._calculate_unpredictability_score(),
            "依恋度": self._get_attachment().current_intimacy
        }

    def _calculate_consistency_score(self) -> float:
        """计算一致性得分"""
        pending_promises = len(self._get_consistency().get_pending_promises())
        # 承诺越少，一致性越高
        return max(0.3, 0.9 - pending_promises * 0.1)

    def _calculate_growth_score(self) -> float:
        """计算成长性得分"""
        topics_learned = len(self._get_user_profile().learned_topics)
        # 话题越多，成长性越高
        return min(0.9, 0.3 + topics_learned * 0.05)

    def _calculate_emotional_score(self) -> float:
        """计算情绪化得分"""
        recent = self._get_emotional_memory().get_recent_moods(7)
        if len(recent) < 3:
            return 0.5

        # 情绪变化越多，情绪化得分越高
        changes = sum(1 for i in range(1, len(recent))
                     if abs(recent[i].mood_value - recent[i-1].mood_value) > 0.1)
        return min(0.9, 0.4 + changes * 0.1)

    def _calculate_vulnerability_score(self) -> float:
        """计算脆弱性得分"""
        stats = self._get_vulnerability().get_vulnerability_stats()
        rate = stats.get("vulnerability_rate", 0)
        # 适度的脆弱（5-15%）最真实
        if 0.05 <= rate <= 0.15:
            return 0.8
        elif 0.02 <= rate <= 0.25:
            return 0.6
        return 0.4

    def _calculate_physical_score(self) -> float:
        """计算身体存在感得分"""
        # 基于是否有环境上下文
        return 0.75  # 基础分

    def _calculate_unpredictability_score(self) -> float:
        """计算不可预测性得分"""
        # 基于是否触发过意外行为
        if self._get_unpredictable().last_surprise_time is None:
            return 0.5  # 尚未触发过意外

        # 基础分 + 基于交互次数
        return min(0.85, 0.6 + self._get_unpredictable().user_interaction_count * 0.01)

    def _value_to_label(self, value: float) -> str:
        """将情绪值转换为标签"""
        if value > 0.7:
            return "开心"
        elif value > 0.5:
            return "舒适"
        elif value > 0.3:
            return "担心"
        else:
            return "低落"
