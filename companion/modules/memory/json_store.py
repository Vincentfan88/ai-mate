"""JSON 文件事实存储 — MVP 实现"""

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .store import MemoryStore, MemoryItem

logger = logging.getLogger(__name__)

# L0 写入门控关键词 — AI 自身属性不写入 L1 事实库
PERSONA_KEYWORDS = [
    "我是", "我叫", "我的名字", "我是谁",
    "我的性格", "我的MBTI", "我的类型",
    "作为一个AI", "作为AI", "我是一个AI"
]


class JsonFactStore(MemoryStore):
    """L1 事实存储 — JSON 文件 + 关键词检索 + 温度排序"""

    # 温度衰减：半衰期 30 天
    TIME_DECAY_HALF_LIFE = 30
    # 清理阈值：温度低于此值的事实定期清理
    COMPACT_THRESHOLD = 0.05

    def __init__(self, facts_path: str = "workspace/companion/memory/facts.json"):
        self.facts_path = Path(facts_path)
        self.facts_path.parent.mkdir(parents=True, exist_ok=True)
        self._facts: List[dict] = self._load()

    # -------------------- 写入 --------------------

    def record(self, content: str, importance: float = None, source: str = "user") -> MemoryItem:
        """写入一条事实，L0 门控检查"""
        # L0 门控：AI 自身属性标记，不混入用户事实
        if source == "ai_attribute" or self._is_persona_content(content):
            item = MemoryItem(
                content=content,
                timestamp=datetime.now().isoformat(),
                importance=importance or 0.1,
                metadata={"source": "ai_attribute"},
            )
            logger.debug(f"[JsonFactStore] 跳过 AI 属性事实: {content}")
            return item

        if importance is None:
            importance = self._estimate_importance(content)

        # 去重：查找相似事实
        existing = self.deduplicate(content)
        if existing:
            existing["mention_count"] += 1
            item = MemoryItem(**existing)
            self._save()
        else:
            fact = {
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "importance": importance,
                "mention_count": 1,
                "related_keywords": [],
                "source": source,
            }
            self._facts.append(fact)
            self._save()
            item = MemoryItem(**fact)

        return item

    def update(self, content: str, **fields) -> None:
        """更新已有事实"""
        for f in self._facts:
            if f["content"] == content:
                f.update(fields)
                self._save()
                return
        logger.warning(f"[JsonFactStore] 未找到事实: {content}")

    # -------------------- 检索 --------------------

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """按关键词匹配 + 温度排序检索"""
        query_set = set(query.lower())

        matched = []
        for f in self._facts:
            content_set = set(f["content"].lower())
            if query_set & content_set:
                matched.append(f)

        # 无匹配时返回全部（宽查询）
        if not matched:
            matched = self._facts

        scored = []
        for f in matched:
            temp = self._compute_temperature(f)
            if temp < self.COMPACT_THRESHOLD:
                continue  # 过滤低温事实
            scored.append({**f, "temperature": round(temp, 3)})

        scored.sort(key=lambda x: x["temperature"], reverse=True)
        return scored[:top_k]

    def get_all(self) -> List[dict]:
        return list(self._facts)

    def deduplicate(self, content: str) -> Optional[dict]:
        """查找相似事实（MVP: 字符集交集 >70%）"""
        content_set = set(content.lower())
        for f in self._facts:
            existing_set = set(f["content"].lower())
            overlap = len(existing_set & content_set)
            if overlap > len(content_set) * 0.7:
                return f
        return None

    # -------------------- 清理 --------------------

    def compact(self) -> int:
        """清理低温事实，返回删除数量"""
        before = len(self._facts)
        self._facts = [
            f for f in self._facts
            if self._compute_temperature(f) >= self.COMPACT_THRESHOLD
        ]
        removed = before - len(self._facts)
        if removed > 0:
            self._save()
        return removed

    # -------------------- 内部方法 --------------------

    def _compute_temperature(self, fact: dict) -> float:
        """温度 = 重要性 × (1 + 提及×0.3) × 时间衰减 × 关联增强"""
        importance = fact.get("importance", 0.3)
        mention_bonus = 1 + fact.get("mention_count", 1) * 0.3

        # 时间衰减
        ts = fact.get("timestamp", "")
        if ts:
            try:
                created = datetime.fromisoformat(ts)
                age_days = (datetime.now() - created).total_seconds() / 86400
            except (ValueError, TypeError):
                age_days = 0
        else:
            age_days = 0
        time_decay = math.exp(-age_days / self.TIME_DECAY_HALF_LIFE)

        # 关联增强
        kw_count = len(fact.get("related_keywords", []))
        relation_bonus = min(0.3, kw_count * 0.05)
        relation_multiplier = 1 + relation_bonus

        return importance * mention_bonus * time_decay * relation_multiplier

    def _estimate_importance(self, content: str) -> float:
        """规则估算重要性"""
        emotional_keywords = ["喜欢", "爱", "讨厌", "开心", "难过", "担心", "害怕", "想", "怕"]
        time_keywords = ["明天", "下周", "以后", "生日", "纪念日", "考试", "面试"]

        score = 0.3
        if any(kw in content for kw in emotional_keywords):
            score += 0.4
        if any(kw in content for kw in time_keywords):
            score += 0.2
        return min(0.9, score)

    def _is_persona_content(self, content: str) -> bool:
        return any(kw in content for kw in PERSONA_KEYWORDS)

    def _load(self) -> List[dict]:
        if self.facts_path.exists():
            try:
                return json.loads(self.facts_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[JsonFactStore] 加载失败: {e}")
        return []

    def _save(self) -> None:
        try:
            self.facts_path.write_text(
                json.dumps(self._facts, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"[JsonFactStore] 保存失败: {e}")

    def get_user_facts(self) -> List[dict]:
        """获取所有用户事实（排除 AI 属性）"""
        return [f for f in self._facts if f.get("source") != "ai_attribute"]

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        """获取最近互动 — JsonFactStore 不存储交互，返回空列表
        （如需完整交互记录，使用 MemorySystem.get_recent_interactions）"""
        return []

    def close(self) -> None:
        pass  # JSON 文件不需要显式关闭
