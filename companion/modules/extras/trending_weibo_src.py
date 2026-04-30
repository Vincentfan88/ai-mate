"""
微博热搜内容源

需要登录 Cookie 才能获取完整数据。
未配置 Cookie 时返回空列表。
"""

import requests
from typing import List, Optional
import logging

from .trending import ContentSource, TrendingItem

logger = logging.getLogger("trending.weibo")

# 微博热搜 API
_WEIBO_HOT_API = "https://weibo.com/ajax/side/hotSearch"

# 默认请求头（可覆盖）
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
    "Accept": "application/json, text/plain, */*",
}


class WeiboHotSource(ContentSource):
    """微博热搜内容源"""

    def __init__(
        self,
        cookie: Optional[str] = None,
        headers: Optional[dict] = None,
        timeout: int = 8,
    ):
        self._cookie = cookie or ""
        self._headers = {**_DEFAULT_HEADERS, **(headers or {})}
        self._timeout = timeout

        # 如果有 cookie，更新 headers
        if self._cookie:
            self._headers["Cookie"] = self._cookie

    @property
    def source_name(self) -> str:
        return "weibo"

    def is_available(self) -> bool:
        """检查微博接口是否可达（不校验 cookie）"""
        if not self._cookie:
            # 无 cookie，认为不可用（数据不完整）
            return False
        try:
            resp = requests.get(
                _WEIBO_HOT_API,
                headers=self._headers,
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_trending(self) -> List[TrendingItem]:
        if not self._cookie:
            logger.warning("[WeiboHotSource] No cookie configured, skipping")
            return []

        try:
            resp = requests.get(
                _WEIBO_HOT_API,
                headers=self._headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            items = []
            for entry in data.get("data", {}).get("realtime", []):
                word = entry.get("word", "")
                if not word:
                    continue

                # 微博热搜有分类标签
                category = entry.get("category", "综合")

                items.append(TrendingItem(
                    source="weibo",
                    title=word,
                    url=f"https://s.weibo.com/weibo?q={word}",
                    rank=entry.get("rank"),
                    category=category,
                ))

            logger.info(f"[WeiboHotSource] Fetched {len(items)} items")
            return items

        except Exception as e:
            logger.warning(f"[WeiboHotSource] Fetch failed: {e}")
            return []