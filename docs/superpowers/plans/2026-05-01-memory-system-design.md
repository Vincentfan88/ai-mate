# 记忆系统设计方案

> AI Companion-ng v2.0 记忆模块完整架构与实现计划
> 版本：1.0 | 日期：2026-05-01

---

## 一、架构概述

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **L0 不存，但要用** | L0 人设通过 system prompt 注入（MVP）/ 微调模型内嵌（生产），记忆模块只读不写 |
| **MD 是源，JSON 是衍生** | MD 文件持久化全量数据，JSON 是计算缓存（可丢失可重算） |
| **MD 是源，JSON 是衍生** | 对话日志优先写入，全量保存不可丢失 |
| **单一模型，三阶段调用** | 同一本地 LLM 顺序执行：提取 → 状态更新 → 生成 |
| **全量检索** | 每条消息都检索，单用户 50ms 延迟无感 |
| **不动源码** | 通过包装类接入 Mini-Agent，不修改其核心代码 |

### 1.2 三层记忆架构

| 层级 | 内容 | 保护策略 | 载体 |
|------|------|----------|------|
| **L0** | AI 核心人设（"我是谁"） | 只读，不可修改 | `persona.json` → system prompt |
| **L1** | 已确认的对话事实（用户说了什么） | 矛盾检测 + 温度索引 | MD 事实文件 + JSON 索引 |
| **L2+** | 偏好推断（AI 主动猜测） | 可更新、可猜错、可遗忘 | `preferences.json` |

### 1.3 调用流程

```
用户消息到达
    │
    ├── 同步路径（~1s 总延迟）
    │   │
    │   1. 提取 LLM（~300ms）
    │      输入: 当前消息 + 最近事实 + 提取 prompt
    │      输出: {"extracted": [...], "contradictions": [...]}
    │
    │   2. 更新 JSON 状态（<1ms）
    │      facts.json + interactions.json 滚动更新
    │
    │   3. 全量检索记忆（<1ms / QMD 50ms）
    │      MVP: 关键词匹配 + 温度排序
    │      Phase 2: QMD 语义检索
    │
    │   4. 组装 context（~1ms）
    │      System:   L0 精简人设       ~300t
    │      Recent:   最近 3 轮完整对话   ~400t
    │      State:    当前状态（JSON）    ~50t
    │      Memory:   检索结果 Top 3     ~200t
    │      Pref:     高置信度偏好 1-2 条 ~100t
    │      Input:    当前消息           ~50t
    │      ───────────────────────────────
    │      注入合计                      ~1050t
    │
    │   5. 生成 LLM（~500ms）
    │      返回回复给用户
    │
    │   6. 同步写 MD（<10ms，append）
    │      conversations/YYYY-MM-DD.md 追加对话
    │      facts/user_facts.md 追加新事实
    │
    └── 异步路径（不阻塞）
        │
        7. 偏好推断 LLM（~300ms，下一条生效）
           从累积事实推断用户偏好
           → preferences.json 更新

        8. 各模块状态更新（纯计算）
           情绪、关系、活人感等
```

---

## 二、存储结构

```
workspace/companion/
│
├── conversations/                    ← P0：全量对话日志（MD，按日期）
│   ├── 2026-05-01.md
│   ├── 2026-05-02.md
│   └── ...
│
├── facts/                            ← P0：事实记录（MD，人类可读）
│   ├── user_facts.md                 ← 用户事实、偏好、关键事件
│   └── key_events.md                 ← 纪念日、重要时间点
│
├── memory/                           ← P0：计算缓存（JSON）
│   ├── facts.json                    ← L1 事实索引（温度/重要性/提及次数）
│   ├── preferences.json              ← L2+ 偏好推断（信念状态/置信度）
│   ├── interactions.json             ← 最近 20 轮缓存（滚动截断）
│   └── l0_persona.json               ← L0 人设参考（从 skills/ 同步，只读）
│
├── states/                           ← 各模块状态（JSON，各自管理）
│   ├── emotion_state.json            ← emotion 模块
│   ├── liveness.json                 ← liveness 模块
│   ├── trigger_state.json            ← trigger 模块
│   └── relationship_state.json       ← relationship 模块
│
├── qmd.yml                           ← Phase 2：QMD 配置
└── index.sqlite                      ← Phase 2：QMD 索引
```

### 文件职责

| 格式 | 用途 | 检索方式 | 人类可读 |
|------|------|----------|----------|
| **MD** | 全量对话日志 + 事实记录 | QMD (Phase 2) | ✅ |
| **JSON** | 结构化计算缓存 | 直接加载解析 | ✅ |

**核心原则**：需要计算的放 JSON，需要阅读的放 MD。JSON 丢了从 MD 可重建。

---

## 三、核心组件

### 3.1 MemoryStore 接口

```python
@dataclass
class MemoryItem:
    """统一记忆条目"""
    content: str
    timestamp: str
    importance: float
    mention_count: int = 1
    metadata: dict = None  # 扩展字段（来源、类型、关联等）


class MemoryStore(ABC):
    """记忆存储接口 — JSON / SQLite / QMD 可插拔"""

    @abstractmethod
    def record(self, content: str, importance: float = None, **kwargs) -> MemoryItem:
        """写入一条事实"""

    @abstractmethod
    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """检索事实，按相关度返回"""

    @abstractmethod
    def get_all(self) -> List[dict]:
        """获取全部事实"""

    @abstractmethod
    def update(self, content: str, **fields) -> None:
        """更新已有事实（提及次数、关联词等）"""

    @abstractmethod
    def deduplicate(self, content: str) -> Optional[dict]:
        """查找相似事实用于去重"""

    @abstractmethod
    def close(self) -> None:
        """清理资源（SQLite/向量库需要）"""


class ConversationLog(ABC):
    """对话日志接口 — MD 文件写入"""

    @abstractmethod
    def append(self, role: str, content: str, timestamp: str) -> None:
        """追加一条对话到当日 MD 文件"""

    @abstractmethod
    def get_recent(self, limit: int = 3) -> List[dict]:
        """获取最近 N 轮对话"""
```

### 3.2 实现类

| 实现类 | 阶段 | 检索方式 | 依赖 |
|--------|------|----------|------|
| `JsonFactStore` | MVP | 关键词匹配 + 温度排序 | 无 |
| `SQLiteFactStore` | Phase 2 | FTS5 全文搜索 | sqlite3（内置） |
| `QmdAdapter` | Phase 3 | BM25 + 向量 + reranking | QMD daemon |

MVP 阶段使用 `JsonFactStore` + `MdConversationLog` 即可。

### 3.3 L0 写入门控

```python
class FactStore(MemoryStore):
    """L1 事实存储 — JSON 索引 + MD 文件双写"""

    # L0 写入门控：AI 自身属性不写入事实库
    PERSONA_KEYWORDS = [
        "我是", "我叫", "我的名字", "我是谁",
        "我的性格", "我的MBTI", "我的类型"
    ]

    def record(self, content: str, importance: float = None, source: str = "user") -> MemoryItem:
        # 门控检查
        if self._is_persona_content(content):
            return self._mark_as_persona(content, importance)

        # 正常写入流程...

    def _is_persona_content(self, content: str) -> bool:
        """判断是否涉及 AI 自身属性"""
        return any(kw in content for kw in self.PERSONA_KEYWORDS)
```

### 3.4 提取 Prompt

```
你是一个善于观察的伙伴。请从用户的消息中提取值得记住的事实。

【什么是值得记的】
- 用户的个人信息（职业、城市、年龄等）
- 用户的偏好（喜欢/讨厌的食物、活动、习惯）
- 用户的情绪状态（最近累、开心、焦虑）
- 用户的重要事件（考试、面试、旅行、纪念日）
- 用户提到的具体时间点（"下周"、"周五"）

【什么不值得记】
- 日常问候（"在吗"、"早安"）
- 简短的语气词（"哈哈"、"嗯"、"好"）
- 反问和疑问（"你说呢？"）
- 重复已知信息

已知事实：{existing_facts}
当前消息：{user_message}

以 JSON 格式输出：
{{
  "extracted": ["新事实1", "新事实2"],
  "contradictions": [{{"new": "...", "old": "...", "reason": "..."}}]
}}
```

### 3.5 Context 组装

| Layer | 内容 | Tokens | 来源 |
|-------|------|--------|------|
| System | L0 精简人设 | ~300t | `l0_persona.json` |
| Recent | 最近 3 轮完整对话 | ~400t | `interactions.json` |
| State | 情绪/关系/HMM 一行 | ~50t | `states/` |
| Memory | 检索到的事实 | ~200t | `MemoryStore.search()` |
| Pref | 高置信度偏好 | ~100t | `preferences.json` |
| Input | 当前消息 | ~50t | 用户输入 |
| **Total** | | **~1050t** | |

---

## 四、已明确的设计决策

| 编号 | 问题 | 决策 |
|------|------|------|
| 1 | 提取 LLM Token 预算 | 10k+ 上下文窗口，无瓶颈 |
| 2 | 模型选择 | 单一本地模型，三阶段顺序调用 |
| 3 | 事实去重 | MVP 放宽，Phase 2 QMD 语义去重 |
| 4 | L0 门控边界 | MVP 标记 source，生产自动解决 |
| 5 | Context 动态调整 | 固定注入，简单可靠 |
| 6 | MD 写入时机 | 同步路径，返回前写入 |
| 7 | 检索触发 | 全量检索，每条消息都跑 |
| 8 | 偏好推断时机 | 异步，下一条生效 |
| 9 | 矛盾检测 | 提取阶段顺带完成（LLM 调用内） |
| 10 | 记忆清理 | 定期 compact 低温事实（温度 < 0.05） |
| 11 | Mini-Agent 集成 | 包装类接管流程，不修改源码 |

---

## 五、实现计划

### Phase 1：MVP 基础架构

1. **存储目录初始化**
   - 创建 `conversations/`、`facts/`、`memory/` 目录
   - 迁移现有 JSON 文件到 `states/`

2. **核心接口定义**
   - `MemoryStore` ABC 接口
   - `ConversationLog` ABC 接口

3. **MVP 实现**
   - `JsonFactStore` — JSON 文件存储 + 关键词检索
   - `MdConversationLog` — MD 对话日志读写
   - `InteractionCache` — 最近 20 轮滚动缓存

4. **MemorySystem 重构**
   - 统一入口，注入 `MemoryStore` + `ConversationLog`
   - L0 persona 加载（只读）
   - 写入门控

5. **Tool 适配器更新**
   - `MemoryTool` 支持新接口
   - `CompanionRegistry` 更新初始化参数

### Phase 2：QMD 接入（待定）

6. **QMD 适配**
   - `QmdAdapter` — HTTP 调用 QMD daemon
   - 检索替换为语义搜索
   - 事实去重用语义向量

### Phase 3：优化

7. **记忆清理**
   - `compact()` 定期清理低温事实
   - 温度阈值自动调节

8. **性能优化**
   - SQLite FTS5 替代 JSON（可选）
   - context 动态调整（可选）

---

## 六、延迟预算

| 步骤 | 耗时 | 同步/异步 |
|------|------|-----------|
| 提取 LLM | ~300ms | 同步 |
| 更新 JSON | <1ms | 同步 |
| 检索记忆 | <1ms（MVP）/ 50ms（QMD） | 同步 |
| 组装 context | ~1ms | 同步 |
| 生成 LLM | ~500ms | 同步 |
| 写 MD 日志 | <10ms | 同步 |
| 偏好推断 | ~300ms | 异步 |
| **总计** | **~1s（同步）** | |

单用户场景 + 本地模型 20-40 token/s，回复生成 5-10s，系统开销 ~1s 无感。
