"""L2+ 偏好推断模块 — 持久化 + 置信度 + 确认/否认 + 衰减 + LLM 推断。"""

import json
import logging
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .fact_store import FactStore

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
    is_negative: bool = False             # 是否为负面推断（会更快衰减）
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def trust_score(self) -> float:
        """trust = confidence * confirm_ratio * recency_factor"""
        total = self.confirm_count + self.deny_count
        if total == 0:
            confirm_ratio = 0.5
        else:
            confirm_ratio = self.confirm_count / total

        if self.last_mentioned_date:
            days_since = (datetime.now() - datetime.fromisoformat(self.last_mentioned_date)).days
        else:
            days_since = (datetime.now() - datetime.fromisoformat(self.created_at)).days

        # 选择性遗忘：负面推断衰减更快（2倍速）
        if self.is_negative:
            recency = max(0.2, 0.95 ** (days_since * 2))
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
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "PreferenceBelief":
        d["state"] = BeliefState(d.get("state", "active"))
        return cls(**d)


# -------------------- 推断 Prompt --------------------

INFERENCE_PROMPT = """你是一个善于观察的伙伴。

根据以下对话内容，主动推断用户的潜在偏好或状态。
只做有依据的推断，不要过度猜测。

规则：
1. 只推断有明显信号支撑的内容
2. 推断应该用自然语言表达，像是人的内心独白
3. 每个推断给出置信度（0.3-0.8之间）
4. 标注基于哪些信号（用户说了什么）

对话内容：
{conversation_text}

格式：
推断内容 | 置信度 | 基于的信号
"""

INFERENCE_EXAMPLE = """
示例：
对话：
用户: 今天加班到十点好累啊
用户: 周末想睡个懒觉
角色: 辛苦啦，要注意身体哦
用户: 对了我想吃顿好的犒劳自己

推断：
"用户最近可能工作压力大，需要放松" | 0.7 | "加班很累、想睡懒觉、犒劳自己"
"用户可能对美食有兴趣" | 0.6 | "想吃顿好的犒劳自己"
"""


class PreferenceInfer:
    """L2+ 偏好推断 — 持久化 + 置信度 + 确认/否认 + 衰减 + LLM 推断"""

    MAX_ACTIVE_BELIEFS = 10
    UNCERTAIN_THRESHOLD = 0.3
    FADING_DAYS = 14
    DISCARD_DAYS = 30

    def __init__(self, fact_store: FactStore, data_path: str = "workspace/companion/preference.json"):
        self.store = fact_store
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._beliefs: List[PreferenceBelief] = self._load_beliefs()

    def _load_beliefs(self) -> List[PreferenceBelief]:
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [PreferenceBelief.from_dict(d) for d in data]
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[PreferenceInfer] 加载推断失败: {e}")
        return []

    def _save_beliefs(self) -> None:
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in self._beliefs], f, ensure_ascii=False, indent=2)
        except (TypeError, OSError) as e:
            logger.error(f"[PreferenceInfer] 保存推断失败: {e}")

    # -------------------- 核心接口（兼容 MemorySystem） --------------------

    def infer(self, llm_client: Any = None) -> dict:
        """从事实中推断偏好，并持久化结果"""
        signals = self._extract_signals()
        if not signals:
            return self._empty_result()

        inferences = self._do_inference(signals, llm_client)

        for content, confidence, sigs in inferences:
            self._add_or_update_belief(content, confidence, sigs)

        self._run_maintenance()
        return self._active_result()

    def _extract_signals(self) -> List[str]:
        """从事实存储中提取近期信号"""
        facts = self.store.get_user_facts()
        interactions = self.store.get_recent_interactions(limit=20)
        signals = []
        for f in facts:
            signals.append(f.get("content", ""))
        for ix in interactions:
            signals.append(f"{ix.get('role', 'user')}: {ix.get('content', '')}")
        return signals

    def _do_inference(
        self,
        signals: List[str],
        llm_client: Any = None,
    ) -> List[Tuple[str, float, List[str]]]:
        if llm_client:
            return self._llm_inference(signals, llm_client)
        return self._rule_based_inference(signals)

    def _llm_inference(
        self,
        signals: List[str],
        llm_client: Any,
    ) -> List[Tuple[str, float, List[str]]]:
        prompt = INFERENCE_PROMPT.format(conversation_text="\n".join(signals)) + "\n\n" + INFERENCE_EXAMPLE
        try:
            response = llm_client.chat([{"role": "user", "content": prompt}])
            return self._parse_inference_response(response)
        except Exception as e:
            logger.warning(f"[PreferenceInfer] LLM 推断失败: {e}")
            return self._rule_based_inference(signals)

    def _rule_based_inference(
        self,
        signals: List[str],
    ) -> List[Tuple[str, float, List[str]]]:
        """基于规则的简单推断"""
        results = []
        signals_text = " ".join(signals)
        rules = [
            (["累", "加班", "疲倦", "好累"], "最近工作疲劳，需要放松", 0.6),
            (["想吃", "饿", "美食"], "可能对美食有兴趣", 0.5),
            (["开心", "高兴", "棒", "顺利"], "心情不错", 0.7),
            (["难过", "伤心", "不开心"], "心情不太好", 0.6),
            (["压力", "焦虑", "担心"], "可能有压力", 0.5),
            (["辣", "火锅", "麻辣"], "喜欢吃辣", 0.7),
            (["咖啡", "奶茶"], "喜欢咖啡/奶茶", 0.6),
            (["电影", "剧", "动漫"], "对影视内容有兴趣", 0.5),
        ]
        for keywords, inference_text, confidence in rules:
            if any(kw in signals_text for kw in keywords):
                results.append((inference_text, confidence, keywords))
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
            if not line or line.startswith("#") or line.startswith("示例"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                content = parts[0].strip().strip('"')
                try:
                    confidence = float(parts[1].strip())
                except ValueError:
                    confidence = 0.5
                sigs = [s.strip() for s in parts[2].split(",")]
                results.append((content, confidence, sigs))
        return results

    def _add_or_update_belief(
        self,
        content: str,
        confidence: float,
        signals: List[str],
    ) -> None:
        """添加或更新信念"""
        # 检查是否已有类似信念（内容匹配）
        for b in self._beliefs:
            if b.state != BeliefState.ACTIVE:
                continue
            if content in b.content or b.content in content:
                b.confirm()
                b.confidence = min(0.95, b.confidence * 0.3 + confidence * 0.7)
                b.source_signals = signals
                self._save_beliefs()
                return

        # 数量上限检查
        active = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        if len(active) >= self.MAX_ACTIVE_BELIEFS:
            sorted_beliefs = sorted(active, key=lambda b: b.trust_score)
            weakest = sorted_beliefs[0]
            self._beliefs.remove(weakest)

        belief = PreferenceBelief(
            id=f"belief_{uuid.uuid4().hex[:12]}",
            content=content,
            target="user",
            confidence=confidence,
            source_signals=signals,
        )
        self._beliefs.append(belief)
        self._save_beliefs()

    def _run_maintenance(self) -> Dict[str, int]:
        """运行维护任务：衰减、过期清理"""
        now = datetime.now()
        stats = {"decayed": 0, "removed": 0, "uncertain": 0}

        for b in self._beliefs:
            if b.state == BeliefState.DISCARDED:
                continue

            if b.last_mentioned_date:
                last_date = datetime.fromisoformat(b.last_mentioned_date)
            else:
                last_date = datetime.fromisoformat(b.created_at)

            days_since = (now - last_date).days

            if days_since >= self.DISCARD_DAYS:
                b.state = BeliefState.DISCARDED
                stats["removed"] += 1
            elif days_since >= self.FADING_DAYS and b.state == BeliefState.ACTIVE:
                b.state = BeliefState.FADING
                stats["decayed"] += 1

            if b.trust_score < self.UNCERTAIN_THRESHOLD and b.state == BeliefState.ACTIVE:
                b.state = BeliefState.UNCERTAIN
                stats["uncertain"] += 1

        self._beliefs = [b for b in self._beliefs if b.state != BeliefState.DISCARDED]
        self._save_beliefs()
        return stats

    def _active_result(self) -> dict:
        """返回当前活跃推断"""
        beliefs = [
            b for b in self._beliefs
            if b.state in (BeliefState.ACTIVE, BeliefState.UNCERTAIN)
        ]
        beliefs.sort(key=lambda b: b.trust_score, reverse=True)

        inferences = []
        for b in beliefs[:5]:
            prefix = "" if b.confidence >= 0.8 else random.choice(["可能", "好像", "不确定是不是"])
            inferences.append(f"{prefix}{b.content}（{b.trust_score:.0%}）")

        categories = {
            "偏好": [],
            "状态": [],
            "习惯": [],
            "其他": [],
        }
        for b in beliefs:
            if any(w in b.content for w in ["喜欢", "爱吃", "兴趣"]):
                categories["偏好"].append(b.content)
            elif any(w in b.content for w in ["心情", "压力", "疲劳"]):
                categories["状态"].append(b.content)
            elif any(w in b.content for w in ["习惯", "每天", "通常"]):
                categories["习惯"].append(b.content)
            else:
                categories["其他"].append(b.content)

        return {
            "inferences": inferences,
            "belief_count": len(beliefs),
            "categories": categories,
        }

    def _empty_result(self) -> dict:
        return {
            "inferences": [],
            "belief_count": 0,
            "categories": {"偏好": [], "状态": [], "习惯": [], "其他": []},
        }

    # -------------------- 显式操作接口 --------------------

    def confirm_belief(self, belief_id: str) -> bool:
        """确认一条推断是正确的"""
        for b in self._beliefs:
            if b.id == belief_id:
                b.confirm()
                self._save_beliefs()
                return True
        return False

    def deny_belief(self, belief_id: str) -> bool:
        """否认一条推断（猜错了）"""
        for b in self._beliefs:
            if b.id == belief_id:
                b.deny()
                self._save_beliefs()
                return True
        return False

    def get_active_beliefs(self, limit: int = 5) -> List[PreferenceBelief]:
        """获取活跃推断"""
        beliefs = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        beliefs.sort(key=lambda b: b.trust_score, reverse=True)
        return beliefs[:limit]

    def get_random_belief(self) -> Optional[PreferenceBelief]:
        """随机获取一条推断（偶发记忆触发）"""
        active = [b for b in self._beliefs if b.state == BeliefState.ACTIVE]
        if not active:
            return None
        if random.random() < 0.15:
            return random.choice(active)
        return None

    def get_inference_context(self, max_beliefs: int = 5) -> str:
        """生成推断上下文文本，注入 LLM prompt"""
        beliefs = [
            b for b in self._beliefs
            if b.state == BeliefState.ACTIVE and b.trust_score >= 0.3
        ]
        beliefs.sort(key=lambda b: b.trust_score, reverse=True)
        beliefs = beliefs[:max_beliefs]

        if not beliefs:
            return ""

        lines = ["[我的观察和猜测]"]
        for b in beliefs:
            if b.confidence < 0.8:
                uncertainty = random.choice(["我猜", "可能", "好像", "不确定是不是"])
                lines.append(f"- {uncertainty}{b.content}（{b.trust_score:.0%}）")
            else:
                lines.append(f"- {b.content}")
        return "\n".join(lines)

    def detect_inconsistency(self, new_user_statement: str) -> Optional[str]:
        """检测用户新陈述是否与已有推断矛盾"""
        new_lower = new_user_statement.lower()
        for b in self._beliefs:
            if b.state != BeliefState.ACTIVE:
                continue
            content_lower = b.content.lower()
            positive_markers = ['喜欢', '想', '要', '爱', '能', '会', '去', '吃']
            for marker in positive_markers:
                if marker in content_lower:
                    neg_patterns = [f'不{marker}', f'不太{marker}', f'没{marker}', f'不想', f'不爱', f'不要']
                    for pattern in neg_patterns:
                        if pattern in new_lower:
                            return f"你之前好像不是这样说的？当时你说{b.content}..."
            opposite_pairs = [
                ('累', ['不累了', '不累', '好多了', '休息了']),
                ('压力大', ['没什么压力', '轻松多了', '好轻松', '很轻松']),
                ('忙', ['不忙了', '有空了', '闲下来了']),
            ]
            for pos_word, neg_phrases in opposite_pairs:
                if pos_word in content_lower and any(np in new_lower for np in neg_phrases):
                    return f"嗯...你之前好像不是这样想的？{b.content}..."
        return None

    def get_stats(self) -> dict:
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
        }
