"""
L2+ 偏好推断层 - Preference Model

从对话中主动推断用户偏好，并维护这些推断。
设计理念：不像精密机器，更像人。

核心概念：
- PreferenceBelief: 一个推断/假设（可能猜错）
- PreferenceModel: 管理所有 L2+ 推断
- 推断可以随时间演化、遗忘、冲突

与 L0/L1 的关系：
- L0: 核心人设（只读，不变）
- L1: 已确认事实（对话中明确说的）
- L2+: 主动推断（可猜错，可更新，可遗忘）

参考：research/memory-management/04-findings.md
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# -------------------- 信任度与状态 --------------------

class BeliefState(Enum):
    """推断状态"""
    ACTIVE = "active"           # 活跃，正在使用
    UNCERTAIN = "uncertain"     # 存疑，需要确认
    FADING = "fading"           # 正在遗忘
    DISCARDED = "discarded"     # 已丢弃


# -------------------- 数据模型 --------------------

@dataclass
class PreferenceBelief:
    """
    一个偏好推断/假设

    特征：
    - 不确定性：可能猜错
    - 时效性：可能过时
    - 可演化：随新信息更新
    - 选择性遗忘：负面记忆衰减更快
    """
    id: str
    content: str                          # 推断内容（自然语言）
    target: str                           # 推断目标（通常是用户）
    confidence: float = 0.5               # 置信度 0-1（1=确定，0.5=猜测）
    state: BeliefState = BeliefState.ACTIVE
    source_signals: List[str] = field(default_factory=list)  # 基于哪些信号推断
    related_fact_ids: List[str] = field(default_factory=list)  # 关联的 L1 事实
    last_mentioned_date: Optional[str] = None
    confirm_count: int = 0                # 被确认次数
    deny_count: int = 0                   # 被否认次数
    decay_rate: float = 0.95              # 自然衰减率
    is_negative: bool = False             # 3.8 是否为负面推断（会更快衰减）
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def trust_score(self) -> float:
        """
        计算信任分数

        trust = confidence * confirm_ratio * recency_factor
        - confidence: 初始置信度
        - confirm_ratio: confirm/(confirm+deny) 或 0.5（无数据时）
        - recency_factor: 随时间衰减（负面推断衰减更快）
        """
        total = self.confirm_count + self.deny_count
        if total == 0:
            confirm_ratio = 0.5
        else:
            confirm_ratio = self.confirm_count / total

        # 时间衰减
        if self.last_mentioned_date:
            days_since = (datetime.now() - datetime.fromisoformat(self.last_mentioned_date)).days
        else:
            days_since = (datetime.now() - datetime.fromisoformat(self.created_at)).days

        # 3.8 选择性遗忘：负面推断衰减更快（2倍速）
        if self.is_negative:
            recency = max(0.2, 0.95 ** (days_since * 2))  # 负面推断更快遗忘
        else:
            recency = max(0.3, 0.95 ** days_since)

        return self.confidence * confirm_ratio * recency

    @property
    def is_verified(self) -> bool:
        """是否被充分验证（猜对次数够多）"""
        return self.confirm_count >= 3

    def confirm(self) -> None:
        """确认这个推断是正确的"""
        self.confirm_count += 1
        self.last_mentioned_date = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        if self.confirm_count >= 3 and self.confidence < 0.9:
            self.confidence = min(0.95, self.confidence + 0.1)

    def deny(self) -> None:
        """否认这个推断（猜错了）"""
        self.deny_count += 1
        self.last_mentioned_date = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        if self.deny_count >= 2:
            self.state = BeliefState.UNCERTAIN
            self.confidence = max(0.3, self.confidence - 0.2)

    def touch(self) -> None:
        """触碰（调用这个推断时调用）"""
        self.last_mentioned_date = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["state"] = self.state.value  # Enum → str
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "PreferenceBelief":
        d["state"] = BeliefState(d.get("state", "active"))
        return cls(**d)


@dataclass
class SocialMemory:
    """
    社交记忆：AI 和用户的互动历史

    区别于 L1 事实（用户说了什么），SocialMemory 记录：
    - AI 推荐了什么、做了什么
    - 用户的反应如何
    """
    id: str
    action: str                           # AI 做了什么
    target: str                           # 动作对象（用户）
    user_reaction: Optional[str] = None   # 用户的反应（confirmed/denied/neutral）
    context: Optional[str] = None         # 上下文
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


# -------------------- 推断生成 Prompt --------------------

INFERENCE_PROMPT = """你是一个善于观察的伙伴。

根据以下对话内容，主动推断用户的潜在偏好或状态。
只做有依据的推断，不要过度猜测。

⚠️ 注意：这些推断是给你的"观察视角"，不是让你朗读出来的脚本。
你用自己的风格自然表达，不要直接说"我猜你..."这样的机械开头。

规则：
1. 只推断有明显信号支撑的内容
2. 推断应该用自然语言表达，像是人的内心独白
3. 每个推断给出置信度（0.3-0.8之间）
4. 标注基于哪些信号（用户说了什么）

对话内容：
{conversation_text}

格式：（仅供内部解析用，输出不要按这个格式直接告诉用户）
推断内容 | 置信度 | 基于的信号

示例：
"用户最近可能工作压力大" | 0.6 | "用户说加班很多、很累"
"用户可能喜欢辣的食物" | 0.7 | "用户主动说想吃火锅、喜欢辣"
"""

INFERENCE_EXAMPLE = """
示例：

对话：
用户: 今天加班到十点好累啊
用户: 周末想睡个懒觉
角色: 辛苦啦，要注意身体哦
用户: 对了我想吃顿好的犒劳自己

推断：
"用户最近工作疲劳，需要放松" | 0.7 | "加班很累、想睡懒觉、犒劳自己"
"用户可能对美食有兴趣" | 0.6 | "想吃顿好的犒劳自己"
"""


# -------------------- PreferenceModel --------------------

class PreferenceModel:
    """
    L2+ 偏好推断模型

    管理 AI 对用户的主动推断，这些推断：
    - 可以猜错（允许错误）
    - 会随时间演化（被确认或否认）
    - 会自然遗忘（长时间不确认则降级）
    - 有数量上限（7±2条活跃推断）

    ⚠️ 重要：这些推断是"AI 的观察视角"，不是脚本：
    - L2+ 提供的是 AI"我猜/我观察到..."的底气
    - AI 用自己的风格自然表达，不是朗读 belief.content
    - 选择当下相关的 1-2 个自然带出，而非列举所有
    - 参考：research/memory-management/04-findings.md

    活人感体现：
    - 3.1 表达不确定性：confidence < 0.8 时显示模糊
    - 3.2 合理遗忘：长时间不确认则降级为 UNCERTAIN
    - 3.6 数量上限：超过 MAX_ACTIVE_BELIEFS 时丢弃最低信任的
    - 3.7 脑补机制：从信号推断多个维度
    - 3.8 选择性遗忘：负面推断更容易被遗忘
    - 3.11 社交属性：记录 AI 的主动行为和用户反应
    - 3.12 随机触发：偶发性调用
    """

    MAX_ACTIVE_BELIEFS = 10          # 活跃推断上限（7±2）
    UNCERTAIN_THRESHOLD = 0.3        # 信任分低于此值则标记为 UNCERTAIN
    FADING_DAYS = 14                 # 多少天不确认则开始衰减
    DISCARD_DAYS = 30                # 多少天不确认则丢弃

    def __init__(
        self,
        data_path: str = "./data/memory",
    ):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # 推断存储文件
        self._beliefs_file = self.data_path / "preference_beliefs.json"
        self._social_file = self.data_path / "social_memories.json"

        self._beliefs: List[PreferenceBelief] = self._load_beliefs()
        self._social_memories: List[SocialMemory] = self._load_social_memories()

        logger.info(f"[PreferenceModel] 加载了 {len(self._beliefs)} 条推断，{len(self._social_memories)} 条社交记忆")

    def _load_beliefs(self) -> List[PreferenceBelief]:
        if self._beliefs_file.exists():
            try:
                with open(self._beliefs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [PreferenceBelief.from_dict(d) for d in data]
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[PreferenceModel] 加载推断失败: {e}")
        return []

    def _save_beliefs(self) -> None:
        try:
            with open(self._beliefs_file, "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in self._beliefs], f, ensure_ascii=False, indent=2)
        except (TypeError, OSError) as e:
            logger.error(f"[PreferenceModel] 保存推断失败: {e}")

    def _load_social_memories(self) -> List[SocialMemory]:
        if self._social_file.exists():
            try:
                with open(self._social_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [SocialMemory(**d) for d in data]
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[PreferenceModel] 加载社交记忆失败: {e}")
        return []

    def _save_social_memories(self) -> None:
        try:
            with open(self._social_file, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in self._social_memories], f, ensure_ascii=False, indent=2)
        except (TypeError, OSError) as e:
            logger.error(f"[PreferenceModel] 保存社交记忆失败: {e}")

    # -------------------- 核心操作 --------------------

    def add_belief(
        self,
        content: str,
        confidence: float = 0.5,
        source_signals: Optional[List[str]] = None,
        related_fact_ids: Optional[List[str]] = None,
        is_negative: bool = False,
    ) -> str:
        """
        添加一个新的推断

        Args:
            content: 推断内容
            confidence: 置信度 0-1
            source_signals: 基于的信号
            related_fact_ids: 关联的 L1 事实 ID
            is_negative: 3.8 是否为负面推断（会更快衰减）

        Returns:
            belief_id
        """
        # 数量上限检查
        active_beliefs = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        if len(active_beliefs) >= self.MAX_ACTIVE_BELIEFS:
            # 丢弃信任分最低的
            sorted_beliefs = sorted(active_beliefs, key=lambda b: b.trust_score)
            weakest = sorted_beliefs[0]
            self._remove_belief(weakest.id)
            logger.info(f"[PreferenceModel] 达到上限，丢弃推断: {weakest.content}")

        belief = PreferenceBelief(
            id=f"belief_{uuid.uuid4().hex[:12]}",
            content=content,
            target="user",
            confidence=confidence,
            source_signals=source_signals or [],
            related_fact_ids=related_fact_ids or [],
            is_negative=is_negative,
        )

        self._beliefs.append(belief)
        self._save_beliefs()
        return belief.id

    def add_social_memory(
        self,
        action: str,
        user_reaction: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        """
        添加社交记忆（AI 的主动行为记录）

        Args:
            action: AI 做了什么
            user_reaction: 用户反应
            context: 上下文

        Returns:
            memory_id
        """
        memory = SocialMemory(
            id=f"social_{uuid.uuid4().hex[:12]}",
            action=action,
            target="user",
            user_reaction=user_reaction,
            context=context,
        )

        self._social_memories.append(memory)
        self._save_social_memories()
        return memory.id

    def infer_from_signals(
        self,
        signals: List[str],
        llm_client: Any = None,
    ) -> List[Tuple[str, float, List[str]]]:
        """
        从信号推断用户偏好

        Args:
            signals: 观察到的信号列表
            llm_client: LLM 客户端

        Returns:
            List[(推断内容, 置信度, 基于的信号)]
        """
        if not llm_client:
            # 无 LLM 时使用规则推断（简化版）
            return self._rule_based_inference(signals)

        prompt = (
            INFERENCE_PROMPT.format(conversation_text="\n".join(signals))
            + INFERENCE_EXAMPLE
        )

        try:
            response = llm_client.chat([{"role": "user", "content": prompt}])
            return self._parse_inference_response(response)
        except Exception as e:
            logger.warning(f"[PreferenceModel] LLM 推断失败: {e}")
            return self._rule_based_inference(signals)

    def _rule_based_inference(
        self,
        signals: List[str],
    ) -> List[Tuple[str, float, List[str]]]:
        """基于规则的简单推断"""
        results = []
        signals_text = " ".join(signals)

        # 简单规则
        rules = [
            (["累", "加班", "疲倦"], "用户可能工作疲劳", 0.6),
            (["想吃", "饿"], "用户可能饿了或对美食有兴趣", 0.5),
            (["开心", "高兴", "棒"], "用户心情不错", 0.7),
            (["难过", "伤心", "不开心"], "用户心情不好", 0.6),
            (["压力", "焦虑", "担心"], "用户可能有压力", 0.5),
        ]

        for keywords, inference, confidence in rules:
            if any(kw in signals_text for kw in keywords):
                results.append((inference, confidence, keywords))

        return results

    def _parse_inference_response(
        self,
        response: str,
    ) -> List[Tuple[str, float, List[str]]]:
        """解析 LLM 返回的推断"""
        results = []
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 解析 "推断 | 置信度 | 信号" 格式
            parts = line.split("|")
            if len(parts) >= 3:
                content = parts[0].strip().strip('"')
                try:
                    confidence = float(parts[1].strip())
                except ValueError:
                    confidence = 0.5
                signals = [s.strip() for s in parts[2].split(",")]
                results.append((content, confidence, signals))

        return results

    def _remove_belief(self, belief_id: str) -> None:
        """移除推断"""
        self._beliefs = [b for b in self._beliefs if b.id != belief_id]

    # -------------------- 查询 --------------------

    def get_active_beliefs(
        self,
        target: Optional[str] = None,
        min_trust: float = 0.0,
        limit: int = 10,
    ) -> List[PreferenceBelief]:
        """
        获取活跃推断

        Args:
            target: 目标过滤（默认 "user"）
            min_trust: 最低信任分数
            limit: 返回数量

        Returns:
            按信任分降序的推断列表
        """
        beliefs = [b for b in self._beliefs if b.state in (BeliefState.ACTIVE, BeliefState.UNCERTAIN)]

        if target:
            beliefs = [b for b in beliefs if b.target == target]

        # 过滤最低信任度
        beliefs = [b for b in beliefs if b.trust_score >= min_trust]

        # 按信任分排序
        beliefs.sort(key=lambda b: b.trust_score, reverse=True)

        return beliefs[:limit]

    def get_random_belief(self) -> Optional[PreferenceBelief]:
        """
        随机获取一条推断（3.12 记忆触发的随机性）

        随机性来源：
        - 不是基于当前话题的逻辑调用
        - 而是像人一样"突然想起"
        """
        active = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        if not active:
            return None

        # 低概率随机选择：2%-18% 随机波动（体现记忆触发的偶发性）
        if random.random() < self._fuzz_probability(0.1, 0.08):
            return random.choice(active)

        return None

    def get_uncertain_beliefs(self) -> List[PreferenceBelief]:
        """获取存疑的推断（需要重新确认的）"""
        return [b for b in self._beliefs if b.state == BeliefState.UNCERTAIN]

    def _fuzz_confidence(self, confidence: float) -> int:
        """
        对显示的置信度加随机扰动，体现人类表达的不精确性。

        - 高置信度（0.8+）：±5% 范围（对自己判断较有信心，范围窄）
        - 中高置信度（0.6-0.8）：±8% 范围
        - 中置信度（0.4-0.6）：±12% 范围
        - 低置信度（<0.4）：±15% 范围（不确定时表达更模糊）

        这样每次显示同一个推断，数字会有细微波动，更像人类表达。
        """
        if confidence >= 0.8:
            delta = 5
        elif confidence >= 0.6:
            delta = 8
        elif confidence >= 0.4:
            delta = 12
        else:
            delta = 15

        fuzz = random.randint(-delta, delta)
        return max(5, min(98, int(confidence * 100) + fuzz))

    def _fuzz_probability(self, base: float, spread: float) -> float:
        """
        对概率值加随机扰动，体现人类行为的不规律性。

        Args:
            base: 基础概率（如 0.3 代表 30%）
            spread: 扰动幅度（如 0.2 代表 ±20% 的波动范围）

        Returns:
            扰动后的概率值， clamped 到 [0.05, 0.95]
        """
        return max(0.05, min(0.95, base + random.uniform(-spread, spread)))

    def get_social_memories(
        self,
        recent_only: bool = True,
        limit: int = 5,
    ) -> List[SocialMemory]:
        """
        获取社交记忆

        Args:
            recent_only: 只返回最近的
            limit: 返回数量
        """
        memories = sorted(self._social_memories, key=lambda m: m.created_at, reverse=True)

        if recent_only:
            memories = [m for m in memories if m.user_reaction is None]

        return memories[:limit]

    def get_inference_context(self, max_beliefs: int = 5) -> str:
        """
        生成推断上下文文本，用于注入 LLM prompt

        ⚠️ 这是给 AI 的"内心独白提示"，AI 用自己的风格自然表达，
        不是直接朗读这些内容。格式仅供参考。

        格式：（AI 看到的内部视角）
        [我的观察和猜测]
        - 我猜你可能...（60%确定）
        - 根据你说的...
        """
        beliefs = self.get_active_beliefs(min_trust=0.3, limit=max_beliefs)

        if not beliefs:
            return ""

        lines = ["[我的观察和猜测]"]
        for b in beliefs:
            # 3.1 表达不确定性
            if b.confidence < 0.8:
                uncertainty = random.choice(["我猜", "可能", "好像", "不确定是不是"])
                display_pct = self._fuzz_confidence(b.confidence)
                content = f"- {uncertainty}你{b.content}（{display_pct}%确定）"
            else:
                content = f"- {b.content}"

            lines.append(content)

        return "\n".join(lines)

    def get_natural_context(self, max_beliefs: int = 3) -> str:
        """
        3.3 时机的自然感：生成"自然流出"的上下文

        与 get_inference_context() 的区别：
        - 不显式说"我记得..."
        - 不显示置信度百分比
        - 用更自然的语气，让 AI 直接带出而不解释来源

        格式：
        [我最近在想]
        - 她好像挺忙的...
        - 那家店她说想去很久了
        """
        beliefs = self.get_active_beliefs(min_trust=0.25, limit=max_beliefs)

        if not beliefs:
            return ""

        lines = ["[我最近在想]"]
        for b in beliefs:
            # 转换为自然的内心独白
            content = b.content
            # 去除"用户"主语，变成更自然的表达
            content = content.replace("用户", "她")
            # 随机选择表达风格
            style = random.choice([
                f"{content}...",
                f"那件事...{content.lower()}",
                f"说起来，{content.lower()}",
            ])
            lines.append(f"- {style}")

        return "\n".join(lines)

    # -------------------- 更新 --------------------

    def confirm_belief(self, belief_id: str) -> bool:
        """确认一条推断是正确的"""
        for b in self._beliefs:
            if b.id == belief_id:
                b.confirm()
                self._save_beliefs()
                logger.info(f"[PreferenceModel] 推断被确认: {b.content}")
                return True
        return False

    def deny_belief(self, belief_id: str) -> bool:
        """否认一条推断（猜错了）"""
        for b in self._beliefs:
            if b.id == belief_id:
                b.deny()
                self._save_beliefs()
                logger.info(f"[PreferenceModel] 推断被否认: {b.content}")
                return True
        return False

    def touch_belief(self, belief_id: str) -> bool:
        """触碰一条推断（被调用时）"""
        for b in self._beliefs:
            if b.id == belief_id:
                b.touch()
                self._save_beliefs()
                return True
        return False

    def get_impulsive_belief(self) -> Optional[PreferenceBelief]:
        """
        3.4 主动出击的冲动：获取"凭直觉"触发的推断

        与 get_random_belief() 的区别：
        - get_random_belief: 纯粹的随机触发（3.12）
        - get_impulsive_belief: 基于"感觉"而非"证据"，直觉性行动

        机制：
        - 选择 trust_score 较低但还没到 UNCERTAIN 的
        - 代表"我有预感但不太确定，先试试看"的状态
        """
        candidates = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        # 筛选"有预感但不确定"的：trust_score 在 0.25-0.45 之间
        candidates = [b for b in candidates if 0.25 <= b.trust_score <= 0.45]

        if not candidates:
            return None

        # 冲动触发概率：15%-45% 随机波动（更符合人类的不规律行为）
        if random.random() < self._fuzz_probability(0.3, 0.15):
            chosen = random.choice(candidates)
            logger.info(f"[PreferenceModel] 冲动触发推断: {chosen.content}")
            return chosen

        return None

    def update_user_reaction(
        self,
        memory_id: str,
        reaction: str,
    ) -> bool:
        """
        更新社交记忆中的用户反应

        Args:
            memory_id: 社交记忆 ID
            reaction: confirmed / denied / neutral
        """
        for m in self._social_memories:
            if m.id == memory_id:
                m.user_reaction = reaction
                m.updated_at = datetime.now().isoformat()

                # 如果被否认，触发相关推断的否认
                if reaction == "denied":
                    self._handle_denial_from_action(m.action)

                self._save_social_memories()
                return True
        return False

    def _handle_denial_from_action(self, action: str) -> None:
        """当用户对一个行为表示否认时，查找相关推断并否认"""
        for b in self._beliefs:
            # 简单匹配：如果推断和 action 相关
            if any(keyword in b.content for keyword in action.split()):
                b.deny()
        self._save_beliefs()

    def get_embarrassed_context(self) -> str:
        """
        3.5 犯错后的尴尬：当 L2+ 猜错时生成"尴尬"反应

        使用场景：
        - LLM 生成回复时引用了不准确的推断
        - 用户指出"你记错了吧"
        - 需要生成一个"有点不好意思"的反应

        返回格式：
        [有点尴尬...]
        - 啊...我好像搞混了
        - 抱歉啊，我记错了
        - 啊对对对，你说的对
        """
        phrases = [
            "啊...我好像搞混了",
            "抱歉啊，我可能记错了",
            "啊对对，你说的对",
            "咦？我记得好像不是这样...",
            "啊...不好意思，我搞错了",
        ]

        return f"[有点尴尬...]\n- {random.choice(phrases)}"

    def get_user_story(self) -> str:
        """
        3.9 记忆的故事化：生成用户的"画像故事"

        将零散的 beliefs 组织成一段叙事性的描述，
        像是"我对这个人的理解"。

        格式：
        [我对她的印象]
        - 她是个工作很拼的人
        - 但最近好像挺累的
        - 喜欢吃辣，偶尔需要犒劳一下自己
        """
        beliefs = self.get_active_beliefs(min_trust=0.2, limit=8)
        if len(beliefs) < 3:
            return ""

        # 按 trust_score 排序，选择最高的几个
        top_beliefs = sorted(beliefs, key=lambda b: b.trust_score, reverse=True)[:5]

        lines = ["[我对她的印象]"]
        for b in top_beliefs:
            content = b.content
            # 去除"用户"主语，变成"她"
            content = content.replace("用户", "她")
            # 只有当内容不以标点或"她"开头时才加前缀
            if not content.endswith("。") and not content.endswith("！") and not content.startswith("她"):
                content = f"她{content}"
            lines.append(f"- {content}")

        return "\n".join(lines)

    def detect_inconsistency(self, new_user_statement: str) -> Optional[str]:
        """
        3.10 跨次记忆的不一致：检测用户新陈述是否与已有推断矛盾

        使用场景：
        - 用户说了与之前不一致的话
        - AI 可以指出"你之前好像不是这么说的"
        - 增加真实感和"被记住"的感觉

        Args:
            new_user_statement: 用户的新陈述

        Returns:
            如果检测到矛盾，返回提示字符串；否则返回 None
        """
        new_lower = new_user_statement.lower()

        # 检查是否有相关的、状态为 ACTIVE 的推断
        for b in self._beliefs:
            if b.state != BeliefState.ACTIVE:
                continue

            content_lower = b.content.lower()

            # 检测矛盾模式
            # 1. 直接否定词对：喜欢 vs 不喜欢/不太喜欢
            # 2. 语义相反：想吃 vs 不想吃/不太想

            # 找出推断中的正向关键词
            positive_markers = ['喜欢', '想', '要', '爱', '能', '会', '去', '吃']
            for marker in positive_markers:
                if marker in content_lower:
                    # 检查用户是否否定了这个
                    # 否定形式：不+marker, 不太+marker, 不太+marker后面的字, 没+marker
                    neg_patterns = [
                        f'不{marker}',
                        f'不太{marker}',
                        f'不太{chr(ord(marker[0]) + 1)}' if len(marker) == 1 else None,  # 不太+下一个字
                        f'没{marker}',
                        f'不想',
                        f'不爱',
                        f'不要',
                    ]
                    for pattern in neg_patterns:
                        if pattern and pattern in new_lower:
                            return f"你之前好像不是这样说的？当时你说{b.content}..."

                    # 额外检查：如果用户说"不太X"但我们有"X"的 belief
                    if marker in new_lower and any(neg in new_lower for neg in ['不太', '不很', '没太', '不怎']):
                        return f"嗯...你之前好像不是这样想的？{b.content}..."

            # 独立检查相反状态对（不依赖于 positive_markers）
            # "不累了" when belief is "需要放松/累"
            # "没什么压力" when belief is "压力大"
            opposite_pairs = [
                ('累', ['不累了', '不累', '好多了', '休息了']),
                ('压力大', ['没什么压力', '不压力大', '轻松了', '轻松多了', '好轻松', '很轻松']),
                ('忙', ['不忙了', '有空了', '闲下来了', '好闲']),
            ]
            for pos_word, neg_phrases in opposite_pairs:
                if pos_word in content_lower and any(np in new_lower for np in neg_phrases):
                    return f"嗯...你之前好像不是这样想的？{b.content}..."

        return None

    # -------------------- 维护 --------------------

    def run_maintenance(self) -> Dict[str, int]:
        """
        运行维护任务：
        - 更新状态（衰减、遗忘）
        - 清理过期推断

        Returns:
            维护报告
        """
        now = datetime.now()
        stats = {"decayed": 0, "removed": 0, "uncertain": 0}

        for b in self._beliefs:
            if b.state == BeliefState.DISCARDED:
                continue

            # 计算天数
            if b.last_mentioned_date:
                last_date = datetime.fromisoformat(b.last_mentioned_date)
            else:
                last_date = datetime.fromisoformat(b.created_at)

            days_since = (now - last_date).days

            # 衰减处理
            if days_since >= self.FADING_DAYS and b.state == BeliefState.ACTIVE:
                b.state = BeliefState.FADING
                stats["decayed"] += 1

            # 丢弃处理
            if days_since >= self.DISCARD_DAYS:
                b.state = BeliefState.DISCARDED
                stats["removed"] += 1

            # 信任分低于阈值则标记为 UNCERTAIN
            if b.trust_score < self.UNCERTAIN_THRESHOLD and b.state == BeliefState.ACTIVE:
                b.state = BeliefState.UNCERTAIN
                stats["uncertain"] += 1

        # 清理完全丢弃的
        self._beliefs = [b for b in self._beliefs if b.state != BeliefState.DISCARDED]

        self._save_beliefs()
        logger.info(f"[PreferenceModel] 维护完成: {stats}")
        return stats

    def get_stats(self) -> Dict:
        """获取统计信息"""
        states = {}
        for b in self._beliefs:
            state_name = b.state.value
            states[state_name] = states.get(state_name, 0) + 1

        return {
            "total_beliefs": len(self._beliefs),
            "active_beliefs": states.get("active", 0),
            "uncertain_beliefs": states.get("uncertain", 0),
            "fading_beliefs": states.get("fading", 0),
            "social_memories": len(self._social_memories),
        }