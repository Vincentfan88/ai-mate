"""
记忆系统模块 — L0/L1/L2+ 三层架构

用法：
    from companion.modules.memory import MemorySystem

    memory = MemorySystem(
        workspace="workspace/companion",
        persona_path="companion/skills/companion/default.json",
    )

    # 记录事实（LLM 提取后调用）
    memory.record("用户喜欢吃辣", importance=0.7)

    # 检索相关记忆
    results = memory.search("喜欢吃什么")

    # 获取最近对话（context 注入用）
    recent = memory.get_recent_conversations(limit=3)
"""

import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from .store import MemoryStore
from .json_store import JsonFactStore
from .md_log import MdConversationLog
from .interaction_cache import InteractionCache
from .preference import PreferenceInfer
from .contradiction import ContradictionDetector

logger = logging.getLogger(__name__)


class MemorySystem:
    """记忆系统统一入口 — L0 只读 + L1 事实 + L2+ 偏好推断"""

    def __init__(
        self,
        workspace: str = "workspace/companion",
        persona_path: Optional[str] = None,
        fact_store: Optional[MemoryStore] = None,
    ):
        self.workspace = workspace

        # L1 事实存储
        self.fact_store = fact_store or JsonFactStore(
            facts_path=f"{workspace}/memory/facts.json"
        )

        # 对话日志
        self.conversation_log = MdConversationLog(
            log_dir=f"{workspace}/conversations"
        )

        # 最近交互缓存
        self.interaction_cache = InteractionCache(
            cache_path=f"{workspace}/memory/interactions.json"
        )

        # L2+ 偏好推断
        self.preference = PreferenceInfer(
            self.fact_store,
            data_path=f"{workspace}/preference.json",
        )

        # 矛盾检测
        self.contradiction = ContradictionDetector()

        # L0 人设（只读）
        self._persona = self._load_persona(persona_path)

    # -------------------- 核心接口 --------------------

    def record(self, content: str, importance: float = None, source: str = "user") -> None:
        """记录一条事实（由提取 LLM 调用）"""
        self.fact_store.record(content, importance, source)

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """检索相关记忆"""
        return self.fact_store.search(query, top_k)

    def get_all_facts(self) -> List[dict]:
        """获取全部事实"""
        return self.fact_store.get_all()

    # -------------------- 对话管理 --------------------

    def add_conversation(self, role: str, content: str, timestamp: str = None) -> None:
        """追加一条对话（同步写入 MD + JSON 缓存）"""
        self.conversation_log.append(role, content, timestamp)
        self.interaction_cache.add(role, content, timestamp)

    def add_conversation_note(self, note: str, timestamp: str = None) -> None:
        """追加一条注释到对话日志"""
        self.conversation_log.append_note(note, timestamp)

    def get_recent_conversations(self, limit: int = 3) -> List[dict]:
        """获取最近 N 轮对话（用于 context 注入）"""
        return self.conversation_log.get_recent(limit)

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        """获取最近交互（JSON 缓存，快速加载）"""
        return self.interaction_cache.get_recent(limit)

    # -------------------- L0 人设（只读） --------------------

    def get_persona_fact(self, key: str) -> str:
        """查询 L0 人设（只读）"""
        if self._persona is None:
            return ""
        # 支持嵌套 key 访问: "personality.core_traits"
        parts = key.split(".")
        value = self._persona
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return ""
        return str(value) if value else ""

    def get_persona_summary(self) -> str:
        """获取 L0 人设摘要（用于 context 注入）"""
        if self._persona is None:
            return ""

        parts = []
        name = self._persona.get("name", "AI")
        desc = self._persona.get("description", "")
        if desc:
            parts.append(f"你是{name}，{desc}")

        # 核心特质
        personality = self._persona.get("personality", {})
        traits = personality.get("core_traits", [])
        if traits:
            parts.append("核心特质：" + "；".join(traits[:3]))

        # 说话风格
        style = self._persona.get("speaking_style", {})
        particles = style.get("particles", [])
        if particles:
            parts.append(f"常用语气词：{', '.join(particles[:5])}")

        return "。".join(parts) + "。"

    # -------------------- 偏好推断 --------------------

    def infer_preferences(self) -> dict:
        return self.preference.infer(llm_client=getattr(self, '_llm_client', None))

    def set_llm_client(self, llm_client: Any) -> None:
        """注入 LLM 客户端（由 registry 代理设置）"""
        self._llm_client = llm_client
        self.preference._llm_client = llm_client

    def check_contradictions(self, facts: Optional[List[dict]] = None) -> List[dict]:
        if facts is None:
            facts = self.fact_store.get_all()
        return self.contradiction.detect(facts)

    # -------------------- 清理 --------------------

    def compact(self) -> int:
        """清理低温事实"""
        return self.fact_store.compact()  # type: ignore[union-attr]

    # -------------------- 内部方法 --------------------

    def _load_persona(self, path: Optional[str]) -> Optional[dict]:
        """加载 L0 人设（只读）"""
        if path is None:
            # 默认路径
            path = "companion/skills/companion/default.json"
        p = Path(path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[MemorySystem] 加载 persona 失败: {e}")
        return None
