"""记忆闪回模块 — 自然提起旧话题，增加活人感。"""

import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .store import MemoryStore


@dataclass
class Flashback:
    """一条闪回提示"""
    fact_id: str
    content: str
    created_at: Optional[str] = None
    follow_up_prompt: str = ""


class FlashbackEngine:
    """记忆闪回引擎 — 在对话中自然提起旧话题。

    触发时机由 LLM 决定（通过 companion_flashback tool），
    内部复用 MemorySystem.search() 做匹配，
    只返回"近期提及但未充分跟进"的高价值记忆。
    """

    # 冷却时间：同一条记忆在冷却期内不再提示（避免重复）
    COOLDOWN_HOURS = 48

    def __init__(self, memory_store: MemoryStore, data_path: str = "workspace/companion/states/flashback_state.json"):
        self._store = memory_store
        self._data_path = data_path
        self._last_flashbacks: List[str] = []  # 格式: [(fact_id, timestamp)]

    def get_flashback(
        self,
        current_message: str,
        top_k: int = 3,
        now: Optional[datetime] = None,
    ) -> List[Flashback]:
        """根据当前消息检索相关记忆，生成闪回提示。

        策略：
        1. 用当前消息检索 MemorySystem.search()
        2. 过滤出"近期创建"的记忆（created_at 距今 < 7天）
        3. 排除冷却期内已提示过的记忆
        4. 生成自然语言跟进提示

        Returns:
            0-3 条 Flashback，按相关性排序
        """
        now = now or datetime.now()

        # 用当前消息检索记忆
        search_results = self._store.search(query=current_message, top_k=10)
        if not search_results:
            return []

        # 应用冷却过滤
        active_flashbacks = self._clean_cooldown(now)
        recent_ids = {fb.fact_id for fb in active_flashbacks}

        flashbacks = []
        for result in search_results:
            fact_id = result.get("id", "")
            content = result.get("content", "")
            if not fact_id or not content:
                continue
            if fact_id in recent_ids:
                continue

            # 检查 created_at（只提示 7 天内创建的记忆）
            created_str = result.get("created_at")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str)
                    days_since = (now - created).total_seconds() / 86400
                    if days_since > 7:
                        continue
                except (ValueError, TypeError):
                    pass

            prompt = self._generate_prompt(content, current_message)
            flashback = Flashback(
                fact_id=fact_id,
                content=content,
                created_at=created_str,
                follow_up_prompt=prompt,
            )
            flashbacks.append(flashback)

            if len(flashbacks) >= top_k:
                break

        # 记录这次闪回（用于冷却）
        for fb in flashbacks:
            self._last_flashbacks.append((fb.fact_id, now.isoformat()))

        # 只保留最近 20 条冷却记录
        if len(self._last_flashbacks) > 20:
            self._last_flashbacks = self._last_flashbacks[-20:]

        return flashbacks

    def _clean_cooldown(self, now: datetime) -> List[Flashback]:
        """清理过期的冷却记录，返回仍在冷却期的 Flashback。"""
        active = []
        remaining = []
        for fact_id, timestamp_str in self._last_flashbacks:
            try:
                ts = datetime.fromisoformat(timestamp_str)
                hours_since = (now - ts).total_seconds() / 3600
                if hours_since < self.COOLDOWN_HOURS:
                    active.append(Flashback(fact_id=fact_id, content=""))
                else:
                    remaining.append((fact_id, timestamp_str))
            except (ValueError, TypeError):
                remaining.append((fact_id, timestamp_str))

        self._last_flashbacks = remaining
        return active

    def _generate_prompt(self, content: str, current_message: str) -> str:
        """根据记忆内容生成自然语言的跟进提示。"""
        templates = [
            "对了，上次你提到「{content}」，后来怎么样了？",
            "想起来，上次你说「{content}」，现在还好吗？",
            "忽然想起，之前你提到「{content}」，有结果了吗？",
        ]
        template = random.choice(templates)
        # 截断过长的内容
        short_content = content[:40] + "..." if len(content) > 40 else content
        return template.format(content=short_content)