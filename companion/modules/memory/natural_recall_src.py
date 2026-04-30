"""
自然记忆召回 - Natural Memory Recall

让记忆"自然地"被想起，而不是机械触发。

核心机制：
1. 遗忘曲线：记忆随时间自然衰减
2. 提及次数加成：越常被提及越容易被想起
3. 周年效应：特定日期附近记忆更容易被唤醒
4. 情感共鸣：当前情绪相关的记忆优先
5. 随机性：加入适度随机，避免机械感
"""

import math
import random
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class MemoryCandidate:
    """候选记忆"""
    memory_id: str
    content: str
    temperature: float       # 综合温度
    base_importance: float   # 基础重要性
    mention_count: int        # 被提及次数
    days_since: int          # 距今天数
    tags: List[str]
    emotion_tag: Optional[str]
    anniversary_bonus: float  # 周年加成
    recall_probability: float # 本次召回概率


class NaturalRecallEngine:
    """
    自然记忆召回引擎

    工作原理：
    1. 获取候选记忆（检索 + 随机采样）
    2. 计算每条记忆的"召回温度"
    3. 按温度排序 + 随机性，选出最终召回的记忆
    4. 附带"为什么想起这条"的解释
    """

    # 遗忘曲线参数（艾宾浩斯风格）
    DECAY_RATE = 0.95          # 每天的衰减率
    DECAY_HALF_LIFE_DAYS = 14  # 半衰期（天）

    # 提及次数加成
    MENTION_BOOST = 0.3        # 每次提及增加的权重

    # 周年效应
    ANNIVERSARY_DAYS = [7, 30, 90, 365]  # 7天、30天、90天、1年

    # 召回概率阈值
    MIN_TEMPERATURE = 0.2        # 最低温度（低于这个不召回）

    def __init__(self, memory_system):
        """
        Args:
            memory_system: HybridMemorySystem 实例
        """
        self.memory_system = memory_system

    def recall(
        self,
        trigger_context: str = "",
        current_emotion: Optional[str] = None,
        max_memories: int = 5,
        randomness: float = 0.3,
        force_recent: bool = False
    ) -> List[MemoryCandidate]:
        """
        自然召回记忆

        Args:
            trigger_context: 触发上下文（用于检索匹配）
            current_emotion: 当前情绪（用于情感共鸣）
            max_memories: 最多召回多少条
            randomness: 随机性强度（0-1），越高越随机
            force_recent: 是否强制包含最近记忆

        Returns:
            召回的记忆列表（带温度和解释）
        """
        now = datetime.now()

        # Step 1: 获取候选记忆
        candidates = self._collect_candidates(trigger_context, current_emotion)

        if not candidates:
            return []

        # Step 2: 计算每条记忆的召回概率
        for candidate in candidates:
            candidate.recall_probability = self._calculate_recall_probability(
                candidate, now, current_emotion, randomness
            )

        # Step 3: 过滤低于阈值的
        candidates = [c for c in candidates if c.recall_probability >= self.MIN_TEMPERATURE]

        # Step 4: 按召回概率排序
        candidates.sort(key=lambda x: x.recall_probability, reverse=True)

        # Step 5: 随机性：加入一些随机采样的记忆
        if randomness > 0 and len(candidates) > max_memories:
            random_count = max(1, int(len(candidates) * randomness))
            sampled = random.sample(candidates, min(random_count, len(candidates)))
            result_ids = {c.memory_id for c in candidates[:max_memories]}
            for item in sampled:
                if item.memory_id not in result_ids:
                    candidates.append(item)
                    result_ids.add(item.memory_id)

            # 重新排序
            candidates.sort(key=lambda x: x.recall_probability, reverse=True)

        # Step 6: 强制包含最近记忆
        if force_recent:
            candidates = self._ensure_recent_memories(candidates, now, max_memories)

        # Step 7: 返回前 N 条
        return candidates[:max_memories]

    def _collect_candidates(
        self,
        trigger_context: str,
        current_emotion: Optional[str]
    ) -> List[MemoryCandidate]:
        """收集候选记忆"""
        candidates = []

        # 从记忆系统获取记忆
        try:
            memories = self.memory_system.get_all_memories()
        except (AttributeError, TypeError):
            return []

        for memory in memories:
            try:
                created = datetime.fromisoformat(memory.date) if memory.date else datetime.now()
            except (ValueError, TypeError):
                created = datetime.now()

            candidate = MemoryCandidate(
                memory_id=memory.id,
                content=memory.content,
                temperature=memory.importance,
                base_importance=memory.importance,
                mention_count=memory.mention_count,
                days_since=(datetime.now() - created).days,
                tags=list(memory.tags) if memory.tags else [],
                emotion_tag=memory.emotion_tag,
                anniversary_bonus=0.0,
                recall_probability=0.0
            )
            candidates.append(candidate)

        # 如果有触发上下文，用记忆系统的检索功能
        if trigger_context:
            try:
                retrieved = self.memory_system.retrieve_memories(
                    trigger_context,
                    current_emotion=current_emotion,
                    limit=20
                )
                # retrieve_memories 可能返回 List[Tuple[Memory, float]] 或 List[Memory]
                retrieved_ids = set()
                for item in retrieved:
                    if isinstance(item, tuple):
                        memory_obj = item[0]
                    else:
                        memory_obj = item
                    retrieved_ids.add(memory_obj.id)

                # 提升检索到的记忆的温度
                for candidate in candidates:
                    if candidate.memory_id in retrieved_ids:
                        candidate.temperature *= 1.5

            except (AttributeError, TypeError, ValueError):
                pass

        return candidates

    def _calculate_recall_probability(
        self,
        candidate: MemoryCandidate,
        now: datetime,
        current_emotion: Optional[str],
        randomness: float
    ) -> float:
        """
        计算召回概率

        公式：温度 = 基础重要性 × 提及加成 × 遗忘衰减 × 周年加成 × 情感共鸣 × 随机因子
        """
        # 基础温度
        temp = candidate.base_importance

        # 提及次数加成（对数衰减，避免无限增长）
        if candidate.mention_count > 0:
            mention_boost = 1 + self.MENTION_BOOST * math.log1p(candidate.mention_count)
            temp *= mention_boost

        # 遗忘曲线（指数衰减）
        days = candidate.days_since
        if days > 0:
            decay_factor = math.pow(self.DECAY_RATE, days / self.DECAY_HALF_LIFE_DAYS)
            temp *= decay_factor

        # 周年效应
        anniversary_bonus = self._check_anniversary(candidate.days_since, candidate.base_importance)
        candidate.anniversary_bonus = anniversary_bonus
        temp += anniversary_bonus

        # 情感共鸣
        if current_emotion and candidate.emotion_tag:
            if self._emotion_matches(current_emotion, candidate.emotion_tag):
                temp *= 1.3

        # 随机性
        if randomness > 0:
            random_factor = 1 + (random.random() - 0.5) * randomness
            temp *= random_factor

        # 归一化到 0-1
        return max(0.0, min(1.0, temp))

    def _check_anniversary(self, days_since: int, importance: float) -> float:
        """检查是否是周年纪念"""
        for ann_days in self.ANNIVERSARY_DAYS:
            if abs(days_since - ann_days) <= 1:  # 误差1天
                return importance * 0.3 * (1 - ann_days / 365)
        return 0.0

    def _emotion_matches(self, current: str, memory: str) -> bool:
        """检查情绪是否匹配"""
        positive = {"开心", "高兴", "快乐", "兴奋"}
        negative = {"难过", "伤心", "痛苦", "沮丧", "焦虑"}
        return (
            current == memory or
            (current in positive and memory in positive) or
            (current in negative and memory in negative)
        )

    def _ensure_recent_memories(
        self,
        candidates: List[MemoryCandidate],
        now: datetime,
        max_count: int
    ) -> List[MemoryCandidate]:
        """确保最近记忆被包含"""
        recent = [c for c in candidates if c.days_since <= 3]
        if not recent:
            return candidates

        result = []
        seen_ids = set()

        for c in sorted(recent, key=lambda x: x.days_since):
            if len(result) < max_count and c.memory_id not in seen_ids:
                result.append(c)
                seen_ids.add(c.memory_id)

        for c in candidates:
            if c.memory_id not in seen_ids and len(result) < max_count:
                result.append(c)
                seen_ids.add(c.memory_id)

        return result

    def generate_recall_explanation(self, candidate: MemoryCandidate) -> str:
        """
        生成召回解释

        解释为什么 AI 会想起这条记忆
        """
        reasons = []

        if candidate.base_importance >= 0.7:
            reasons.append("这件事对你很重要")

        if candidate.mention_count >= 3:
            reasons.append(f"之前聊过{candidate.mention_count}次")
        elif candidate.mention_count >= 1:
            reasons.append("最近提过")

        if candidate.anniversary_bonus > 0.1:
            for ann_days in self.ANNIVERSARY_DAYS:
                if abs(candidate.days_since - ann_days) <= 1:
                    if ann_days == 7:
                        reasons.append("刚好一周了")
                    elif ann_days == 30:
                        reasons.append("刚好一个月了")
                    elif ann_days == 90:
                        reasons.append("三个月了")
                    elif ann_days == 365:
                        reasons.append("一周年了")
                    break

        if candidate.days_since == 0:
            reasons.append("今天发生的事")
        elif candidate.days_since == 1:
            reasons.append("昨天的事")

        if not reasons:
            reasons.append("想到了一些事")

        return "，".join(reasons)


def format_recall_context(
    candidates: List[MemoryCandidate],
    recall_engine: NaturalRecallEngine,
    include_explanation: bool = False
) -> str:
    """
    格式化召回记忆为上下文文本
    """
    if not candidates:
        return ""

    lines = ["【相关记忆】"]

    for i, candidate in enumerate(candidates, 1):
        tag_str = f"[{','.join(candidate.tags)}]" if candidate.tags else ""
        mention_str = f"（聊过{candidate.mention_count}次）" if candidate.mention_count > 0 else ""

        line = f"{i}. {candidate.content} {tag_str}{mention_str}"
        lines.append(line)

        if include_explanation:
            explanation = recall_engine.generate_recall_explanation(candidate)
            lines.append(f"   💭 {explanation}")

    return "\n".join(lines)
