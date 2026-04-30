"""
Trending Content Source System

Content sources: Weibo, Zhihu, Douyin, Xiaohongshu, etc.
User interest matching and caching.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import logging
import random
import threading

logger = logging.getLogger("trending")


@dataclass
class TrendingItem:
    """单条热搜/热榜内容"""
    source: str           # "weibo" / "zhihu" / "douyin" / "xiaohongshu"
    title: str            # 热搜标题
    url: Optional[str]    # 原文链接
    rank: Optional[int]   # 排名
    category: str          # 分类标签，如 "科技" / "游戏" / "娱乐"
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url or "",
            "rank": self.rank or 0,
            "category": self.category,
            "fetched_at": self.fetched_at,
        }


class ContentSource(ABC):
    """内容源抽象接口"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """内容源名称"""
        pass

    @abstractmethod
    def fetch_trending(self) -> List[TrendingItem]:
        """抓取当前热榜内容，返回列表"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查内容源是否可用（网络通畅、认证有效等）"""
        pass


class CachedTrendingStore:
    """
    用户热搜缓存

    每天抓取一次，匹配用户兴趣后缓存，
    供 SceneLibrary 主动聊天时挑选话题。
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._cache: List[TrendingItem] = []
        self._cache_date: Optional[str] = None  # "YYYY-MM-DD"
        self._matched_items: List[TrendingItem] = []
        self._lock = threading.Lock()

    def _is_today(self) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._cache_date == today

    def store(self, items: List[TrendingItem]) -> None:
        """缓存热搜列表"""
        with self._lock:
            self._cache = items
            self._cache_date = datetime.now().strftime("%Y-%m-%d")
            self._matched_items = []
        logger.info(f"[TrendingCache] Stored {len(items)} items for {self._cache_date}")

    def get_matched(
        self,
        user_interests: List[str],
        limit: int = 5,
    ) -> List[TrendingItem]:
        """
        获取匹配用户兴趣的热搜内容

        Args:
            user_interests: 用户兴趣标签列表，如 ["原神", "数码", "旅游"]
            limit: 返回条数上限

        Returns:
            匹配成功的TrendingItem列表（按相关度排序）
        """
        with self._lock:
            if not self._is_today():
                return []

            if self._matched_items:
                return self._matched_items[:limit]

            # 关键词匹配
            interests_lower = [i.lower() for i in user_interests]
            scored = []
            for item in self._cache:
                match_count = sum(1 for interest in interests_lower if interest.lower() in item.title.lower())
                if match_count == 0:
                    continue
                # 匹配关键词越多分数越高，再按排名排序
                score = match_count * 10 + (0 if (item.rank or 999) > 10 else 1)
                scored.append((score, item.rank or 999, item))

            scored.sort(key=lambda x: (-x[0], x[1]))
            self._matched_items = [item for _, _, item in scored]
            return self._matched_items[:limit]

    def get_random_matched(
        self,
        user_interests: List[str],
    ) -> Optional[TrendingItem]:
        """随机获取一条匹配的热搜（用于主动聊天切入）"""
        matched = self.get_matched(user_interests, limit=20)
        if not matched:
            return None
        return random.choice(matched)

    def invalidate(self) -> None:
        """手动失效缓存，强制下次重新抓取"""
        self._cache_date = None
        self._cache = []
        self._matched_items = []

    @property
    def cache_date(self) -> Optional[str]:
        return self._cache_date


class ContentSourceManager:
    """
    内容源管理器

    管理多个内容源，按优先级尝试抓取，
    直到有一个成功为止。
    """

    def __init__(self):
        self._sources: dict[str, ContentSource] = {}
        self._store = CachedTrendingStore()

    def register(self, source: ContentSource) -> None:
        self._sources[source.source_name] = source

    def fetch_all(self, user_interests: List[str]) -> List[TrendingItem]:
        """
        尝试所有已注册的内容源，抓取并缓存

        Returns:
            第一个成功（且非空）的内容源的TrendingItem列表
            如果全部失败，返回空列表
        """
        for name, source in self._sources.items():
            try:
                items = source.fetch_trending()
                # 空列表不算成功，继续尝试下一个源
                if not items:
                    logger.info(f"[ContentSourceManager] {name} returned empty, trying next source")
                    continue
                self._store.store(items)
                logger.info(f"[ContentSourceManager] {name} fetched {len(items)} items")
                return items
            except Exception as e:
                logger.warning(f"[ContentSourceManager] {name} fetch failed: {e}")
                continue

        logger.warning("[ContentSourceManager] All sources failed")
        return []

    def get_today_matched(self, user_interests: List[str], limit: int = 5) -> List[TrendingItem]:
        """获取今日已缓存的匹配内容"""
        return self._store.get_matched(user_interests, limit)

    def get_random_matched(self, user_interests: List[str]) -> Optional[TrendingItem]:
        """随机获取一条匹配内容"""
        return self._store.get_random_matched(user_interests)

    def refresh(self, user_interests: List[str]) -> bool:
        """
        主动刷新缓存

        Returns:
            是否成功刷新
        """
        return bool(self.fetch_all(user_interests))


# 默认全局实例
content_source_manager = ContentSourceManager()