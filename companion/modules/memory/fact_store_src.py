"""
事实存储 - Fact Store

从对话中提取、结构化存储事实，并支持上下文注入。

解决的问题：红豆糕问题（角色不自创没发生过的事）

架构：
- FactStore：事实提取 + 存储 + 检索
- 事实存储在 MemoryDatabase（复用已有基础设施）
- persona 初始事实从 persona JSON 预加载
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.stores.memory import MemoryDatabase

from core.stores.memory import MemoryDatabase, Memory

logger = logging.getLogger(__name__)


# -------------------- 数据模型 --------------------

@dataclass
class Fact:
    """事实单元"""
    id: str
    content: str                          # 事实内容（自然语言描述）
    subject: str                          # 主体（角色/用户）
    source_type: str                      # user | assistant | persona
    turn_id: Optional[int] = None        # 来源对话轮次
    importance: float = 0.6               # 重要性（事实通常比一般记忆重要）
    tags: List[str] = field(default_factory=list)
    confirmed: bool = True                # 是否已确认（提取后默认为 true）
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_memory_dict(self) -> Dict:
        """转换为 MemoryDatabase 兼容的字典"""
        return {
            "id": self.id,
            "content": self.content,
            "importance": self.importance,
            "mention_count": 0,
            "last_mentioned_date": None,
            "tags": self.tags + ["fact", f"source:{self.source_type}", f"subject:{self.subject}"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "event_type": "fact",
            "emotion_tag": None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_context_line(self) -> str:
        """转换为上下文字符串"""
        subject_label = "用户" if self.subject == "user" else "角色"
        return f"[{subject_label}事实] {self.content}"


@dataclass
class Contradiction:
    """矛盾记录"""
    id: str
    fact1_id: str
    fact2_id: str
    fact1_content: str
    fact2_content: str
    description: str                      # 矛盾描述
    resolution: Optional[str] = None      # 解决方式（None=未解决）
    detected_at: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()


# -------------------- 事实提取 Prompt --------------------

FACT_EXTRACTION_PROMPT = """你是一个精确的事实提取器。

从以下对话中提取所有关于角色和用户的重要事实。

规则：
1. 只提取明确陈述的事实，不做推断
2. 事实应该是可验证的陈述（不是观点、情绪、假设）
3. 每条事实单独一行
4. 格式：[主体] [事实内容]

主体分类：
- "角色"：角色（AI）说关于自己的事
- "用户"：用户（人）说关于自己的事

对话内容：
{conversation_text}

提取的事实："""

FACT_EXTRACTION_EXAMPLE = """
示例：

对话：
用户: 我最喜欢吃红豆糕
角色: 那下次我带给你尝尝
用户: 好啊，我特别爱吃甜的

提取的事实：
角色: 表示愿意给用户带红豆糕
用户: 最喜欢吃红豆糕
用户: 特别爱吃甜的
"""


# -------------------- FactStore --------------------

class FactStore:
    """
    事实存储系统

    管理角色和用户的factual knowledge，
    解决"角色不自创没发生过的事"的问题。

    存储：使用 MemoryDatabase（fact_type='fact' tag）
    矛盾检测：ContradictionDetector（独立模块）
    """

    # 矛盾关系关键词（用于快速检测）
    NEGATION_PATTERNS = [
        ("喜欢", "讨厌"),
        ("爱吃", "不爱吃"),
        ("会", "不会"),
        ("有", "没有"),
        ("可以", "不可以"),
        ("愿意", "不愿意"),
        ("知道", "不知道"),
        ("认识", "不认识"),
        ("去过", "没去过"),
        ("做过", "没做过"),
    ]

    def __init__(
        self,
        memory_db: "MemoryDatabase",
        data_path: str = "./data/memory",
    ):
        self._db = memory_db
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # 矛盾记录文件
        self._contradictions_file = self.data_path / "facts_contradictions.json"
        self._contradictions: List[Dict] = self._load_contradictions()

        # persona 初始事实（从 persona JSON 加载）
        self._persona_facts_loaded = False

    def _load_contradictions(self) -> List[Dict]:
        if self._contradictions_file.exists():
            try:
                with open(self._contradictions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[FactStore] 加载矛盾记录失败: {e}")
        return []

    def _save_contradictions(self) -> None:
        try:
            with open(self._contradictions_file, "w", encoding="utf-8") as f:
                json.dump(self._contradictions, f, ensure_ascii=False, indent=2)
        except (TypeError, OSError) as e:
            logger.error(f"[FactStore] 保存矛盾记录失败: {e}")

    # -------------------- 初始化 --------------------

    def initialize_from_persona(self, persona: Dict) -> int:
        """
        从 persona JSON 初始化角色事实

        Args:
            persona: persona JSON 字典（符合 templates/persona/persona-json-schema.md）

        Returns:
            加载的事实数量
        """
        if self._persona_facts_loaded:
            logger.info("[FactStore] persona 事实已加载，跳过")
            return 0

        facts_loaded = 0

        # 1. 从 background.key_memories 加载
        background = persona.get("background", {})
        key_memories = background.get("key_memories", [])
        for memory in key_memories:
            self.add_fact(
                content=memory,
                subject="assistant",
                source_type="persona",
                importance=0.9,
                tags=["persona_memory", "background"],
            )
            facts_loaded += 1

        # 2. 从 personality_tags 加载（作为性格事实）
        profile = persona.get("profile", {})
        personality_tags = profile.get("personality_tags", [])
        for tag in personality_tags:
            self.add_fact(
                content=f"角色性格标签：{tag}",
                subject="assistant",
                source_type="persona",
                importance=0.7,
                tags=["persona", "personality"],
            )
            facts_loaded += 1

        # 3. 从 vulnerability.key_weaknesses 加载
        vulnerability = persona.get("vulnerability", {})
        key_weaknesses = vulnerability.get("key_weaknesses", [])
        for weakness in key_weaknesses:
            self.add_fact(
                content=f"角色核心弱点：{weakness}",
                subject="assistant",
                source_type="persona",
                importance=0.8,
                tags=["persona", "vulnerability"],
            )
            facts_loaded += 1

        # 4. 从 speech.catchphrases 加载（性格事实）
        speech = persona.get("speech", {})
        catchphrases = speech.get("catchphrases", [])
        tone = speech.get("tone", "")
        if tone:
            self.add_fact(
                content=f"角色说话风格：{tone}",
                subject="assistant",
                source_type="persona",
                importance=0.6,
                tags=["persona", "speech_style"],
            )
            facts_loaded += 1
        for cp in catchphrases[:3]:  # 最多加载 3 个
            self.add_fact(
                content=f"角色口头禅：{cp}",
                subject="assistant",
                source_type="persona",
                importance=0.5,
                tags=["persona", "catchphrase"],
            )
            facts_loaded += 1

        self._persona_facts_loaded = True
        logger.info(f"[FactStore] 从 persona 加载了 {facts_loaded} 条事实")
        return facts_loaded

    # -------------------- 核心操作 --------------------

    def add_fact(
        self,
        content: str,
        subject: str,
        source_type: str,
        turn_id: Optional[int] = None,
        importance: float = 0.6,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        添加一条事实

        Returns:
            fact_id
        """
        fact = Fact(
            id=f"fact_{uuid.uuid4().hex[:12]}",
            content=content,
            subject=subject,
            source_type=source_type,
            turn_id=turn_id,
            importance=importance,
            tags=tags or [],
        )

        # 写入 MemoryDatabase
        self._db.add_memory(
            Memory(**fact.to_memory_dict())
        )

        # 快速矛盾检测（基于关键词）
        self._quick_contradiction_check(fact)

        return fact.id

    def extract_and_add_facts(
        self,
        dialogue_text: str,
        source_type: str,
        llm_client: Any = None,
    ) -> List[str]:
        """
        从对话文本中提取事实并添加

        Args:
            dialogue_text: 对话文本（格式：用户: xxx\n角色: xxx）
            source_type: 事实来源类型（user=用户说的事实，assistant=角色说的事实）
            llm_client: LLM 客户端（用于 LLM 提取）

        Returns:
            新添加的 fact_id 列表
        """
        if not llm_client:
            # 无 LLM 时使用启发式提取
            return self._heuristic_extract(dialogue_text, source_type)

        # LLM 提取
        prompt = (
            FACT_EXTRACTION_PROMPT.format(conversation_text=dialogue_text)
            + FACT_EXTRACTION_EXAMPLE
        )

        try:
            response = llm_client.chat([{"role": "user", "content": prompt}])
            fact_lines = self._parse_fact_response(response)
        except Exception as e:
            logger.warning(f"[FactStore] LLM 提取失败，回退到启发式: {e}")
            return self._heuristic_extract(dialogue_text, source_type)

        fact_ids = []
        for line in fact_lines:
            fact_id = self.add_fact(
                content=line,
                subject="user" if source_type == "user" else "assistant",
                source_type=source_type,
                importance=0.6,
                tags=["extracted"],
            )
            fact_ids.append(fact_id)

        return fact_ids

    def _parse_fact_response(self, response: str) -> List[str]:
        """解析 LLM 返回的事实列表"""
        lines = response.strip().split("\n")
        facts = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过标题行和注释
            if line.startswith("#") or line.startswith("示例") or line.startswith("提取的"):
                continue
            # 移除行首的序号和标点
            if line[0].isdigit():
                dot_idx = line.find(".")
                if dot_idx > 0 and dot_idx < 5:
                    line = line[dot_idx + 1:].strip()
            # 移除行首的 "- " 或 "* "
            if line.startswith("- ") or line.startswith("* "):
                line = line[2:].strip()
            if line:
                facts.append(line)
        return facts

    def _heuristic_extract(
        self,
        dialogue_text: str,
        source_type: str,
    ) -> List[str]:
        """
        启发式事实提取（无 LLM 时的备选方案）

        规则：
        - 用户/角色明确说"我XXX" → 提取为事实
        - 检测否定模式 → 提取为否定事实
        """
        fact_ids = []
        lines = dialogue_text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue

            role_part, content_part = line.split(":", 1)
            content = content_part.strip()

            # 提取第一人称陈述
            if any(f"{pron} " in content for pron in ["我", "我的", "I ", "I'm", "I am"]):
                # 清理第一人称
                for pron in ["我", "我的"]:
                    content = content.replace(pron, "角色" if "assistant" in role_part else "用户")
                fact_id = self.add_fact(
                    content=content,
                    subject="assistant" if "assistant" in role_part.lower() else "user",
                    source_type=source_type,
                    importance=0.5,
                    tags=["heuristic"],
                )
                fact_ids.append(fact_id)

        return fact_ids

    # -------------------- 查询 --------------------

    def get_facts(
        self,
        subject: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Fact]:
        """
        获取事实列表

        Args:
            subject: 主体过滤（assistant/user）- 直接过滤 Fact.subject 字段
            source_type: 来源类型过滤（user/assistant/persona）
            limit: 返回数量上限

        Returns:
            Fact 列表
        """
        # 通过 MemoryDatabase 查询（过滤 fact_type）
        all_memories = self._db.get_all_memories()
        facts = []

        for mem in all_memories:
            if "fact" not in mem.tags:
                continue

            # 从 tags 中提取 source_type
            source = None
            for tag in mem.tags:
                if tag.startswith("source:"):
                    source = tag[7:]
                    break

            if source_type and source != source_type:
                continue

            # subject 过滤 - 通过 subject:{value} tag
            if subject:
                subject_tag = f"subject:{subject}"
                if subject_tag not in mem.tags:
                    continue

            # 构造 Fact 对象
            # subject 从 subject:{value} tag 中提取
            fact_subject = None
            for tag in mem.tags:
                if tag.startswith("subject:"):
                    fact_subject = tag[8:]
                    break

            fact = Fact(
                id=mem.id,
                content=mem.content,
                subject=fact_subject or "unknown",
                source_type=source or "unknown",
                importance=mem.importance,
                tags=[t for t in mem.tags if not t.startswith(("fact", "source:", "subject:"))],
                created_at=mem.created_at,
                updated_at=mem.updated_at,
            )
            facts.append(fact)

        facts.sort(key=lambda f: f.importance, reverse=True)
        return facts[:limit]

    def get_persona_facts(self) -> List[Fact]:
        """获取 persona 初始事实"""
        return self.get_facts(source_type="persona")

    def get_user_facts(self) -> List[Fact]:
        """获取用户事实"""
        return self.get_facts(subject="user", source_type="user")

    def get_assistant_facts(self) -> List[Fact]:
        """获取角色事实（来自对话，非 persona 初始）"""
        all_assistant = self.get_facts(subject="assistant")
        return [f for f in all_assistant if f.source_type != "persona"]

    def get_fact_context(self, max_facts: int = 10) -> str:
        """
        生成事实上下文文本，用于注入 LLM prompt

        格式：
        [角色事实]
        - 事实1
        - 事实2
        [用户事实]
        - 事实3
        """
        persona_facts = self.get_facts(source_type="persona", limit=max_facts)
        user_facts = self.get_facts(subject="user", source_type="user", limit=max_facts)

        lines = []

        if persona_facts:
            lines.append("[角色已知事实]")
            for f in persona_facts:
                lines.append(f"  - {f.content}")

        if user_facts:
            lines.append("[用户已分享的事实]")
            for f in user_facts:
                lines.append(f"  - {f.content}")

        return "\n".join(lines) if lines else ""

    def get_all_facts_for_check(self) -> List[Fact]:
        """获取所有事实（用于矛盾检测）"""
        return self.get_facts(limit=500)

    # -------------------- 矛盾检测集成 --------------------

    def _quick_contradiction_check(self, new_fact: Fact) -> Optional[Contradiction]:
        """
        快速矛盾检测（基于关键词，不调用 LLM）

        策略：基于"话题 + 否定"匹配。
        如果已有事实是"[话题]喜欢/爱吃X"，
        新回复包含"不喜欢/不爱吃X"则触发矛盾。
        """
        content_lower = new_fact.content.lower()

        existing_facts = self.get_all_facts_for_check()
        for existing in existing_facts:
            if existing.id == new_fact.id:
                continue
            if existing.subject != new_fact.subject:
                continue  # 只检测同一主体的矛盾

            existing_lower = existing.content.lower()

            # 检测直接否定模式：已有事实包含正向词，新回复包含负向词
            for pos_word, neg_word in self.NEGATION_PATTERNS:
                # 检查"爱吃X" vs "不太爱X"的情况
                # 逻辑：提取已有事实中正向词后面的话题词
                #       检查新回复中是否有"不+正向词"或单独的否定词

                # 检查已有事实是否有正向关键词
                if pos_word not in existing_lower:
                    continue

                # 新回复中是否出现否定词+话题的组合
                negation_words = ["不", "没", "从不", "从来不", "没有", "不太"]
                for neg in negation_words:
                    # 检测"不+正向词"如"不喜欢"、"不爱"等
                    combined_neg = f"{neg}{pos_word[0]}"  # 不+第一个字
                    if combined_neg in content_lower or neg in content_lower:
                        return self._record_contradiction(
                            new_fact, existing,
                            f"新回复否定'{pos_word}'相关，但已有事实确认'{pos_word}'"
                        )

        return None

        return None

    def _record_contradiction(
        self,
        fact1: Fact,
        fact2: Fact,
        description: str,
    ) -> Contradiction:
        """记录矛盾"""
        contradiction = Contradiction(
            id=f"contra_{uuid.uuid4().hex[:12]}",
            fact1_id=fact1.id,
            fact2_id=fact2.id,
            fact1_content=fact1.content,
            fact2_content=fact2.content,
            description=description,
        )

        self._contradictions.append(asdict(contradiction))
        self._save_contradictions()

        logger.warning(
            f"[FactStore] 检测到矛盾: {description}\n"
            f"  事实1: {fact1.content}\n"
            f"  事实2: {fact2.content}"
        )

        return contradiction

    def get_contradictions(self) -> List[Contradiction]:
        """获取所有矛盾记录"""
        return [Contradiction(**c) for c in self._contradictions]

    def resolve_contradiction(
        self,
        contradiction_id: str,
        resolution: str,
    ) -> bool:
        """
        解决矛盾

        Args:
            contradiction_id: 矛盾 ID
            resolution: 解决方式描述

        Returns:
            是否成功
        """
        for c in self._contradictions:
            if c["id"] == contradiction_id:
                c["resolution"] = resolution
                self._save_contradictions()
                return True
        return False

    # -------------------- 快照（用于失忆剧情） --------------------

    def take_snapshot(self, trigger: str = "manual") -> str:
        """
        拍摄事实快照（用于失忆剧情）

        Returns:
            snapshot_id
        """
        snapshot = {
            "snapshot_id": f"snap_{uuid.uuid4().hex[:12]}",
            "trigger": trigger,
            "created_at": datetime.now().isoformat(),
            "persona_facts": [
                asdict(f) for f in self.get_persona_facts()
            ],
            "user_facts": [
                asdict(f) for f in self.get_user_facts()
            ],
        }

        snapshot_file = self.data_path / f"fact_snapshot_{snapshot['snapshot_id']}.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        logger.info(f"[FactStore] 快照已保存: {snapshot['snapshot_id']}")
        return snapshot["snapshot_id"]

    def restore_snapshot(self, snapshot_id: str) -> int:
        """
        恢复事实快照（失忆后重建）

        Returns:
            恢复的事实数量
        """
        snapshot_file = self.data_path / f"fact_snapshot_{snapshot_id}.json"
        if not snapshot_file.exists():
            logger.error(f"[FactStore] 快照不存在: {snapshot_id}")
            return 0

        with open(snapshot_file, "r", encoding="utf-8") as f:
            snapshot = json.load(f)

        restored = 0

        # 恢复 persona 事实（标记为残留）
        for fact_dict in snapshot.get("persona_facts", []):
            # 检查是否已存在
            existing = self._db.get_memory(f"fact_{fact_dict['id']}")
            if not existing:
                self._db.add_memory(Memory(**{
                    "id": f"fact_{fact_dict['id']}",
                    "content": fact_dict["content"],
                    "importance": fact_dict.get("importance", 0.6),
                    "mention_count": 0,
                    "last_mentioned_date": None,
                    "tags": fact_dict.get("tags", []) + ["snapshot_residual", "fact"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "event_type": "fact",
                    "emotion_tag": None,
                    "created_at": fact_dict.get("created_at", datetime.now().isoformat()),
                    "updated_at": datetime.now().isoformat(),
                }))
                restored += 1

        logger.info(f"[FactStore] 快照恢复完成: {restored} 条事实")
        return restored

    def list_snapshots(self) -> List[Dict]:
        """列出所有快照"""
        snapshots = []
        for f in self.data_path.glob("fact_snapshot_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    snapshots.append({
                        "snapshot_id": data["snapshot_id"],
                        "trigger": data["trigger"],
                        "created_at": data["created_at"],
                        "fact_count": len(data.get("persona_facts", [])) + len(data.get("user_facts", [])),
                    })
            except (json.JSONDecodeError, OSError):
                continue

        snapshots.sort(key=lambda s: s["created_at"], reverse=True)
        return snapshots
