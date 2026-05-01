"""最近交互缓存 — 滚动维护的 JSON 文件"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

MAX_INTERACTIONS = 20


class InteractionCache:
    """最近 N 轮对话的 JSON 缓存，用于快速 context 注入"""

    def __init__(self, cache_path: str = "workspace/companion/memory/interactions.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._interactions: List[dict] = self._load()

    def add(self, role: str, content: str, timestamp: str = None) -> None:
        """添加一条交互，滚动截断"""
        self._interactions.append({
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.now().isoformat(),
        })
        # 滚动截断
        if len(self._interactions) > MAX_INTERACTIONS:
            self._interactions = self._interactions[-MAX_INTERACTIONS:]
        self._save()

    def get_recent(self, limit: int = 5) -> List[dict]:
        """获取最近 N 条交互"""
        return self._interactions[-limit:]

    def get_all(self) -> List[dict]:
        return list(self._interactions)

    def clear(self) -> None:
        self._interactions = []
        self._save()

    def _load(self) -> List[dict]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[InteractionCache] 加载失败: {e}")
        return []

    def _save(self) -> None:
        try:
            self.cache_path.write_text(
                json.dumps(self._interactions, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"[InteractionCache] 保存失败: {e}")
