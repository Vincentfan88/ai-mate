"""记忆存储抽象接口 — JSON / SQLite / QMD 可插拔"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MemoryItem:
    """统一记忆条目"""
    content: str
    timestamp: str
    importance: float = 0.3
    mention_count: int = 1
    related_keywords: list = None
    metadata: dict = None
    source: str = "user"

    def __post_init__(self):
        if self.related_keywords is None:
            object.__setattr__(self, "related_keywords", [])
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


class MemoryStore(ABC):
    """记忆存储接口"""

    @abstractmethod
    def record(self, content: str, importance: float = None, source: str = "user") -> MemoryItem:
        """写入一条事实"""

    @abstractmethod
    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """检索事实，按相关度返回"""

    @abstractmethod
    def get_all(self) -> List[dict]:
        """获取全部事实"""

    @abstractmethod
    def update(self, content: str, **fields) -> None:
        """更新已有事实"""

    @abstractmethod
    def deduplicate(self, content: str) -> Optional[dict]:
        """查找相似事实用于去重"""

    @abstractmethod
    def get_user_facts(self) -> List[dict]:
        """获取所有用户事实（排除 AI 属性）"""

    @abstractmethod
    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        """获取最近互动记录"""

    @abstractmethod
    def close(self) -> None:
        """清理资源"""


class ConversationLog(ABC):
    """对话日志接口"""

    @abstractmethod
    def append(self, role: str, content: str, timestamp: str) -> None:
        """追加一条对话到当日日志"""

    @abstractmethod
    def append_note(self, note: str, timestamp: str) -> None:
        """追加一条注释（记忆提取/情绪等）"""

    @abstractmethod
    def get_recent(self, limit: int = 3) -> List[dict]:
        """获取最近 N 轮对话"""
