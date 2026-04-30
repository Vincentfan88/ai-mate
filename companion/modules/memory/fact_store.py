"""温度驱动的记忆存储与检索模块。"""

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Fact:
    content: str
    timestamp: str
    importance: float
    mention_count: int = 1
    related_keywords: List[str] = field(default_factory=list)

    @property
    def age_days(self) -> float:
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds() / 86400

    def compute_temperature(self) -> float:
        """温度 = 基础重要性 × (1 + 提及次数×0.3) × 时间衰减 × 关联增强"""
        base = self.importance
        mention_bonus = 1 + self.mention_count * 0.3
        # 时间衰减：半衰期 30 天
        time_decay = math.exp(-self.age_days / 30)
        # 关联增强：每个关联词 +0.05，最多 +0.3
        relation_bonus = min(0.3, len(self.related_keywords) * 0.05)
        relation_multiplier = 1 + relation_bonus

        return base * mention_bonus * time_decay * relation_multiplier


class FactStore:
    """温度驱动的记忆存储与检索"""

    def __init__(self, store_path: str = "workspace/companion/memory_store.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.write_text(json.dumps({"facts": [], "interactions": []}))

    def record(self, content: str, importance: float = None) -> Fact:
        """记录一条事实"""
        if importance is None:
            importance = self._estimate_importance(content)

        data = self._load()
        # Check if fact already exists (deduplicate)
        existing = self._find_similar(data["facts"], content)
        if existing:
            existing["mention_count"] += 1
            fact = Fact(**existing)
        else:
            fact = Fact(
                content=content,
                timestamp=datetime.now().isoformat(),
                importance=importance,
            )
            data["facts"].append(asdict(fact))

        self._save(data)
        return fact

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """按温度排序检索"""
        data = self._load()
        facts = data.get("facts", [])

        # Keyword matching
        matched = []
        query_words = set(query.lower())
        for f in facts:
            content_words = set(f["content"].lower())
            if query_words & content_words:
                matched.append(f)

        # If no keyword match, return all (for broad queries)
        if not matched:
            matched = facts

        # Sort by temperature
        scored = []
        for f in matched:
            fact = Fact(**f)
            scored.append({
                **f,
                "temperature": round(fact.compute_temperature(), 3),
            })

        scored.sort(key=lambda x: x["temperature"], reverse=True)
        return scored[:top_k]

    def get_user_facts(self) -> List[dict]:
        """获取所有用户事实"""
        data = self._load()
        return data.get("facts", [])

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        """获取最近互动"""
        data = self._load()
        interactions = data.get("interactions", [])
        return interactions[-limit:]

    def add_interaction(self, role: str, content: str, timestamp: str = None):
        """添加一条互动记录"""
        data = self._load()
        data["interactions"].append({
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.now().isoformat(),
        })
        # Keep last 100 interactions
        if len(data["interactions"]) > 100:
            data["interactions"] = data["interactions"][-100:]
        self._save(data)

    def _estimate_importance(self, content: str) -> float:
        """自动估算重要性"""
        emotional_keywords = ["喜欢", "爱", "讨厌", "开心", "难过", "担心", "害怕", "想", "怕", "重要"]
        time_keywords = ["明天", "下周", "以后", "生日", "纪念日", "考试", "面试"]

        score = 0.3  # base
        if any(kw in content for kw in emotional_keywords):
            score += 0.4
        if any(kw in content for kw in time_keywords):
            score += 0.2

        return min(0.9, score)

    def _find_similar(self, facts: List[dict], content: str) -> Optional[dict]:
        """查找相似事实（用于增加提及次数）"""
        content_set = set(content.lower())
        for f in facts:
            if len(set(f["content"].lower()) & content_set) > len(content_set) * 0.7:
                return f
        return None

    def _load(self) -> dict:
        return json.loads(self.store_path.read_text())

    def _save(self, data: dict):
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
