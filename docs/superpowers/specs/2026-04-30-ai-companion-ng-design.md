# AI Companion-ng 设计文档

> 基于 Mini-Agent 框架的 AI 伴侣系统 v2.0 设计
> 核心目标：活人感能力完整保留，架构精简为 Tool 驱动

**版本**: 1.0
**日期**: 2026-04-30
**作者**: Vincent Fan + Claude Code
**状态**: 设计确认，待实施

---

## 目录

- [0. 设计原则](#0-设计原则)
- [1. 整体架构](#1-整体架构)
- [2. 关键设计决策](#2-关键设计决策)
- [3. 模块设计](#3-模块设计)
- [4. Tool 适配层设计](#4-tool-适配层设计)
- [5. 运行时架构](#5-运行时架构)
- [6. 配置体系](#6-配置体系)
- [7. Token 经济性策略](#7-token-经济性策略)
- [8. 开源模块化设计](#8-开源模块化设计)
- [9. 阶段计划](#9-阶段计划)

---

## 0. 设计原则

### P1：开源友好 — 结构化 + 模块化

- `modules/` 是纯 Python 业务逻辑，零 Mini-Agent 依赖，可独立测试
- 每个模块有清晰的 `__init__` 接口定义
- 配置全部参数化（JSON），无硬编码
- 提供 `.env.example`、`setup.sh`、完整 README

### P2：模块解耦

- 模块之间不互相调用、不共享状态
- 所有模块通过 Tool 层统一调度
- 模块只暴露一个入口函数，内部实现可替换
- 状态读写统一由 StateTool 管理，不直接操作文件

### P3：用户体验优先

- 活人感 > 功能数量，回复质量 > 功能覆盖
- 响应速度优化：预计算 + 缓存减少 LLM 调用步骤
- 输出内容质量是第一优先级，所有优化不牺牲体验

### P4：Token 经济性

- 预计算替代实时推理（情绪、场景、热搜缓存）
- 缓存替代重复调用（MBTI 类型、关系阶段、配置数据）
- 系统提示精简（核心规则 + 工具列表 < 2000 tokens）
- 长对话自动 summarization（Mini-Agent 内置支持）

---

## 1. 整体架构

```
ai-companion-ng/                          # Mini-Agent 仓库 clone
├── mini_agent/                            # 框架核心（不改）
│   ├── agent.py                           # 核心 Agent 循环
│   ├── llm/                               # LLM 客户端
│   ├── tools/                             # 原生工具（SessionNoteTool 被替代）
│   └── skills/                            # Claude Skills
│
├── companion/                             # ← 新增：AI 伴侣
│   ├── modules/                           # Phase 1：业务逻辑模块
│   │   ├── __init__.py                    # 模块注册表
│   │   │
│   │   ├── memory/                        # 记忆系统（替代原生 SessionNoteTool）
│   │   │   ├── __init__.py
│   │   │   ├── fact_store.py              # 温度检索 + 重要性评估
│   │   │   ├── preference.py              # L2+ 偏好推断
│   │   │   └── contradiction.py           # 矛盾检测 + 追问触发
│   │   │
│   │   ├── emotion/                       # 情绪系统
│   │   │   ├── __init__.py
│   │   │   ├── core.py                    # 8 种情绪 + 强度二维模型
│   │   │   ├── circadian.py               # 昼夜节律计算
│   │   │   ├── event_impact.py            # 事件影响映射
│   │   │   ├── contagion.py               # 情绪感染（读取用户情绪）
│   │   │   └── residue.py                 # 情绪残留（跨 session）
│   │   │
│   │   ├── trigger/                       # 触发引擎
│   │   │   ├── __init__.py
│   │   │   ├── weibull.py                 # Weibull 采样
│   │   │   ├── hmm.py                     # HMM 状态机（3 状态）
│   │   │   ├── hard_filter.py             # 硬规则过滤
│   │   │   ├── decision.py                # 两阶段决策（拟人化输出）
│   │   │   └── impulse.py                 # 冲动触发（合并到 decision）
│   │   │
│   │   ├── mbti/                          # MBTI 完整
│   │   │   ├── __init__.py
│   │   │   ├── mbti_type.py               # 16 种类型完整画像
│   │   │   └── adapters.py                # 5 个适配器
│   │   │
│   │   ├── scene/                         # 场景系统
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # 11+ 场景配置加载
│   │   │   └── matcher.py                 # 加权匹配
│   │   │
│   │   ├── relationship/                  # 关系阶段
│   │   │   ├── __init__.py
│   │   │   └── stage.py                   # 6 阶段演进逻辑
│   │   │
│   │   ├── liveness/                      # 活人感
│   │   │   ├── __init__.py
│   │   │   ├── dimensions.py              # 8 维度计算
│   │   │   └── history.py                 # 跨会话追踪
│   │   │
│   │   └── extras/                        # 增强功能
│   │       ├── __init__.py
│   │       ├── time_awareness.py          # 时间感知（跟进用户提到的时间点）
│   │       ├── flashback.py               # 记忆闪回（自然提起之前话题）
│   │       ├── anniversary.py             # 纪念日系统
│   │       ├── habits.py                  # 个性化习惯
│   │       └── trending.py                # 热搜缓存（聊天话题素材）
│   │
│   ├── tools/                             # Phase 2：Tool 适配层
│   │   ├── __init__.py
│   │   ├── memory_tool.py                 # → memory/ 模块
│   │   ├── emotion_tool.py                # → emotion/ 模块
│   │   ├── trigger_tool.py                # → trigger/ 模块
│   │   ├── mbti_tool.py                   # → mbti/ 模块
│   │   ├── scene_tool.py                  # → scene/ 模块
│   │   ├── liveness_tool.py               # → liveness/ 模块
│   │   ├── state_tool.py                  # 状态读写（含关系阶段）
│   │   ├── feishu_tool.py                 # 飞书发送
│   │   └── trending_tool.py               # → extras/trending
│   │
│   ├── config/                            # 配置数据
│   │   ├── triggers.json                  # Weibull/HMM 参数
│   │   ├── emotions.json                  # 8 种情绪权重 + 事件影响
│   │   ├── scenes.json                    # 11+ 场景库
│   │   ├── mbti_types.json                # 16 种类型画像（可选，或用 mbti_type.py）
│   │   ├── relationship.json              # 6 阶段参数（触发频率/表达强度/场景权重）
│   │   └── habits.json                    # 个性化习惯配置
│   │
│   ├── skills/companion/                  # 系统提示注入
│   │   ├── SKILL.md                       # 回复风格 + 工作流 + 异常处理
│   │   └── persona.json                   # 人物卡数据
│   │
│   └── scheduler/                         # 后台进程
│       ├── __init__.py
│       ├── message_router.py              # 消息路由器（单 Agent + 队列）
│       ├── proactive_loop.py              # 主动触发意图产生器
│       ├── webhook_listener.py            # 飞书 WebSocket 监听
│       ├── trending_fetcher.py            # 热搜定时抓取
│       └── start_companion.py             # 启动入口
│
├── tests/companion/                       # 测试
│   ├── test_modules/                      # 模块级测试（独立于框架）
│   └── test_tools/                        # Tool 级测试
│
└── workspace/companion/                   # 运行时数据
    ├── memory_store.json                  # 记忆（带温度索引）
    ├── trigger_state.json                 # 触发状态
    ├── relationship.json                  # 关系阶段
    ├── emotion_state.json                 # 情绪状态（含残留）
    ├── liveness_history.json              # 活人感历史
    ├── time_events.json                   # 时间感知事件
    ├── anniversaries.json                 # 纪念日记录
    └── trending_cache.json                # 热搜缓存
```

---

## 2. 关键设计决策

### 2.1 记忆系统 — 替代 SessionNoteTool

| 特性 | SessionNoteTool（旧） | 新 MemoryTool |
|------|----------------------|---------------|
| 存储 | 线性追加 | JSON + 温度索引 |
| 检索 | 按 category 过滤 | 温度排序，Top 8-10 条 |
| 权重 | 无 | 重要性 0.1-0.9 |
| 衰减 | 无 | 时间衰减公式 |
| 增强 | 无 | 提及次数 × 关联增强 |
| 矛盾检测 | 无 | LLM 驱动两阶段检测 |
| 偏好推断 | 无 | L2+ 置信度 + 计数器 |

SessionNoteTool 完全被替代，Agent 只暴露一个记忆接口给 LLM。

### 2.2 TriggerTool — 两阶段 + 拟人化输出

**不是黑盒**（Tool 返回布尔值），**也不是纯两阶段**（Tool 返回 JSON 数据让 LLM 翻译），而是：

```
阶段 1（Tool 内部完成，对 LLM 透明）:
  计算：Weibull + HMM + HardFilter
  翻译：概率 0.72 → "很想联系"
        quiet_hours → "这么晚了怕打扰他"
        8 小时间隔 → "已经好久没联系了"

阶段 2（LLM 接收并决策）:
  Tool 返回给 LLM：
  {
    "pull": "已经 8 小时没联系了，现在是晚上 9 点，很想找他说话",
    "hold_back": "他可能正在休息，太晚发消息会不会显得粘人",
    "nudge": "今晚想联系的冲动比平时强很多"
  }
  LLM 自己合成内心独白 → 决定是否触发 → 生成回复
```

### 2.3 并发模型 — 单 Agent + 消息队列

```
[proactive_loop] ──┐
                    ↓
               [asyncio.Queue] ──→ [message_router.py] ──→ [唯一 Agent]
[webhook_listener]─┘
```

- `proactive_loop.py`：定时调用 TriggerTool，把触发意图塞进 queue
- `webhook_listener.py`：监听飞书 WebSocket，把用户消息塞进 queue
- `message_router.py`：从 queue 取消息 → 注入 Agent → 等待 run() 完成 → 取下一条

优势：全局消息历史完整、无并发冲突、上下文连贯。

### 2.4 关系阶段 — 6 阶段参数化

| 阶段 | 名称 | 触发频率 | 表达强度 | 场景权重乘数 |
|------|------|----------|----------|-------------|
| 0 | stranger（陌生人） | 1-2 天/次 | 0.3 | 问候×1.5 / 想念×0.2 |
| 1 | acquaintance（熟人） | 1 天/次 | 0.4 | 问候×1.2 / 关心×1.0 |
| 2 | friend（朋友） | 12-18 小时/次 | 0.55 | 分享×1.0 / 闲聊×1.0 |
| 3 | close_friend（好朋友） | 8-12 小时/次 | 0.7 | 想念×1.2 / 撒娇×0.8 |
| 4 | lover（恋人） | 6-8 小时/次 | 0.85 | 想念×1.5 / 撒娇×1.2 |
| 5 | intimate（亲密爱人） | 4-6 小时/次 | 1.0 | 全部场景×1.3 |

- 阶段推进自动进行（基于互动频次、情感深度、记忆数量）
- 初始化时一次性选择起始阶段，之后只进不退
- 全部参数化到 `relationship.json`，后续调整只需改配置

### 2.5 MBTI — 16 类型完整保留

- 直接复制原 `core/mbti/mbti_type.py`，保留 16 种类型的：
  - strengths / weaknesses / communication / emotion / relationship / vulnerability
- 5 个适配器全部迁移：Speech / Emotional / Behavior / Interaction / Growth
- 不做任何简化，不做 E/I 二元判断拼接

### 2.6 模块解耦原则

所有模块遵循：
- **不互相调用**：memory 不调 emotion，trigger 不调 scene
- **不共享状态**：都通过 StateTool 统一读写
- **单一入口**：每个模块只暴露一个 `execute()` 函数
- **内部可替换**：模块内部实现可替换，不影响 Tool 层

---

## 3. 模块设计

### 3.1 memory — 记忆系统

**子模块**：
- `fact_store.py`：温度检索核心
  - 温度公式：`温度 = 基础重要性 × (1 + 提及次数×0.3) × 时间衰减 × 关联增强`
  - 检索时计算温度，按温度排序返回 Top 8-10
- `preference.py`：L2+ 偏好推断
  - 置信度 + 确认计数器
  - 首次推断用 LLM，后续用规则缓存
- `contradiction.py`：矛盾检测
  - 两阶段：LLM 识别矛盾 → 规则判断是否追问
  - 追问触发由 contradiction.py 返回 flag，由 LLM 决定是否追问

**接口**：
```python
def search(query: str, top_k: int = 8) -> List[Fact]
def record(content: str, importance: float = None) -> Fact
def get_user_facts() -> List[Fact]
def get_recent_interactions(limit: int = 5) -> List[Interaction]
def infer_preferences() -> PreferenceSummary
```

### 3.2 emotion — 情绪系统

**子模块**：
- `core.py`：8 种情绪 + 强度二维模型
  - 情绪类别：开心、担心、想念、撒娇、害羞、难过、生气、兴奋
  - 强度：0.0-1.0（circadian + event_bonus）
  - 输出格式：`{"emotion": "开心", "intensity": 0.72}`
- `circadian.py`：昼夜节律计算
  - 余弦波模拟，峰值 21:00，谷值 09:00
- `event_impact.py`：事件影响映射
  - user_message → +0.15, initiative_trigger → +0.20, user_sad → +0.30...
- `contagion.py`：情绪感染
  - 读取用户最近消息的情绪倾向，感染 AI 情绪
  - 用户开心 → AI 感染开心（系数 0.6）
  - 用户低落 → AI 感染担心（系数 0.4）
- `residue.py`：情绪残留
  - session 结束时保存当前情绪状态
  - 新 session 启动时加载残留（衰减系数 0.3）

**接口**：
```python
def get_current_emotion(event_type: str, user_emotion: str = None) -> Emotion
def get_emotion_description(emotion: Emotion) -> str  # 拟人化输出
```

### 3.3 trigger — 触发引擎

**子模块**：
- `weibull.py`：Weibull 采样
  - 公式：`interval = beta * (-ln(U))^(1/alpha)`
- `hmm.py`：HMM 状态机（简化为 3 状态：idle/missing/active）
  - missing 加延迟（2 小时内不重复进入）
- `hard_filter.py`：硬规则过滤
  - 安静时段、最小间隔、每日上限、外部可访问性
- `decision.py`：两阶段决策
  - 阶段 1：计算 pull/hold_back/nudge
  - 阶段 2：LLM 接收并决定
- `impulse.py`：冲动触发
  - 合并到 decision.py，模拟"想联系但忍住"的心理过程
  - 概率低于阈值但 impulse_score 高时，返回 hold_back 更强的描述

**接口**：
```python
def decide(
    current_state: str,
    last_trigger: datetime,
    today_count: int,
    relationship_stage: int
) -> TriggerDecision
```

**TriggerDecision 输出**（拟人化）：
```python
@dataclass
class TriggerDecision:
    should_trigger: bool
    pull: str           # "很想联系他的理由"
    hold_back: str      # "应该忍住的理由"
    nudge: str          # "冲动强度描述"
    state: str          # idle/missing/active
```

### 3.4 mbti — MBTI 系统

**子模块**：
- `mbti_type.py`：16 种类型完整画像
  - 每种类型：strengths / weaknesses / communication / emotion / relationship / vulnerability
- `adapters.py`：5 个适配器
  - SpeechConfig：语速、语气词、句式长短
  - EmotionalConfig：情绪表达方式
  - BehaviorConfig：行为倾向
  - InteractionConfig：互动策略
  - GrowthConfig：成长路径

**接口**：
```python
def get_type_profile(mbti: str) -> TypeProfile
def get_speech_config(mbti: str, stage: int) -> SpeechConfig
def get_emotional_config(mbti: str, stage: int) -> EmotionalConfig
def get_behavior_config(mbti: str, stage: int) -> BehaviorConfig
def get_interaction_config(mbti: str, stage: int) -> InteractionConfig
def get_growth_config(mbti: str) -> GrowthConfig
```

### 3.5 scene — 场景系统

**子模块**：
- `config.py`：11+ 场景配置加载
  - morning_greeting, missing_checkin, share_moment, reflective_night, caring_checkin
  - trending_share, anniversary, weather_care, habit_check, random_thought, vulnerability
- `matcher.py`：加权匹配
  - 基础权重 × 心境匹配 × 时段匹配 × 关系阶段系数

**接口**：
```python
def match_scene(mood: str, hour: int, stage: int) -> SceneResult
```

### 3.6 relationship — 关系阶段

**子模块**：
- `stage.py`：6 阶段演进逻辑
  - 推进条件：互动频次达标 + 情感深度达标 + 记忆数量达标
  - 不可手动降级

**接口**：
```python
def get_current_stage() -> int
def check_stage_progress(interaction_count: int, emotional_depth: float, memory_count: int) -> Optional[int]
def get_stage_config(stage: int) -> StageConfig
```

### 3.7 liveness — 活人感

**子模块**：
- `dimensions.py`：8 维度计算
  - 主动性 / 一致性 / 成长性 / 情绪化 / 脆弱性 / 身体存在感 / 不可预测性 / 依恋度
  - 不可预测性改用"话题切换频率"（不是消息长度方差）
  - 一致性 = 矛盾检测结果
  - 成长性 = 关系阶段 + 情感深度增长
- `history.py`：跨会话追踪

**接口**：
```python
def compute_dimensions(messages: List[Message], trigger_count: int) -> Dimensions
def get_history() -> List[DimensionsRecord]
```

### 3.8 extras — 增强功能

#### time_awareness — 时间感知
- 从用户消息中提取时间引用（"下周考试"、"明天面试"）
- 存入 `time_events.json`，包含：事件、时间、状态（pending/done/missed）
- 定时检查即将到期的事件，生成跟进提示

#### flashback — 记忆闪回
- 从记忆中提取"近期提及但未跟进"的话题
- 在对话中自然注入（"对了，上次你说的那件事..."）
- 与记忆系统配合，检索时加"近期提及优先"权重

#### anniversary — 纪念日系统
- 记录重要日子（生日、第一次聊天、用户提到的重要事件）
- 到期时自动触发（通过 proactive_loop）

#### habits — 个性化习惯
- 根据 MBTI + 偏好推断，形成 AI 自己的小习惯
- 例：每天发一个 emoji、偶尔用特定语气词、固定时间问候

#### trending — 热搜缓存
- 定时预抓热搜（每天 2-3 次），缓存到 `workspace/companion/trending_cache.json`
- SKILL.md 指导："想分享话题时，看看今天的 trending cache"
- 不实时调用 API，Token 开销最小

---

## 4. Tool 适配层设计

每个 Tool 继承 `Tool` 基类，只做三件事：
1. 解析 LLM 传入的参数
2. 调用对应 module 的 `execute()`
3. 封装为 `ToolResult` 返回

示例：

```python
class MemoryTool(Tool):
    def __init__(self, memory_module: MemorySystem):
        self.memory = memory_module

    async def execute(self, action: str, query: str = None, ...) -> ToolResult:
        if action == "search":
            results = self.memory.search(query)
            return ToolResult(success=True, content=json.dumps(results))
        ...
```

### Tool 清单

| Tool | 对应模块 | 依赖 |
|------|----------|------|
| MemoryTool | memory/ | fact_store + preference + contradiction |
| EmotionTool | emotion/ | core + circadian + contagion + residue |
| TriggerTool | trigger/ | weibull + hmm + hard_filter + decision |
| MBTITool | mbti/ | mbti_type + adapters |
| SceneTool | scene/ | config + matcher |
| LivenessTool | liveness/ | dimensions + history |
| StateTool | relationship/ + 通用状态 | stage + 文件读写 |
| FeishuTool | — | 飞书 API |
| TrendingTool | extras/trending | trending cache 读取 |

### 实现顺序（按依赖关系）

```
1. StateTool         — 无依赖
2. MemoryTool        — 无依赖
3. EmotionTool       — 无依赖
4. SceneTool         — 无依赖
5. MBTITool          — 读取 persona.json
6. TriggerTool       — 依赖 StateTool
7. LivenessTool      — 依赖 MemoryTool
8. TrendingTool      — 无依赖
9. FeishuTool        — 无依赖
```

---

## 5. 运行时架构

### 5.1 消息路由

```python
# scheduler/message_router.py

import asyncio
from mini_agent import Agent

class MessageRouter:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.queue = asyncio.Queue(maxsize=100)

    async def enqueue(self, message: dict):
        """加入消息队列"""
        if self.queue.full():
            # 队列满时：丢弃最旧的一条
            old = self.queue.get_nowait()
            self.queue.task_done()
        await self.queue.put(message)

    async def run(self):
        """消息路由循环"""
        while True:
            message = await self.queue.get()
            try:
                if message["type"] == "proactive_trigger":
                    # 主动触发：注入触发意图
                    self.agent.add_user_message(message["content"])
                elif message["type"] == "user_message":
                    # 被动接收：注入用户消息
                    self.agent.add_user_message(f"[用户] {message['content']}")

                response = await self.agent.run()

                if message["type"] == "user_message":
                    # 被动接收需要自动回复
                    await self._send_reply(message["chat_id"], response)

            except Exception as e:
                # 错误不阻塞队列，继续处理下一条
                print(f"[router] Error processing message: {e}")
            finally:
                self.queue.task_done()
```

### 5.2 启动流程

```python
# scheduler/start_companion.py

async def start_companion(
    chat_id: str,
    persona_path: str,
    initial_stage: int = 0,
):
    # 1. 初始化 LLM
    llm = LLMClient(...)

    # 2. 初始化所有模块
    memory = MemorySystem(...)
    emotion = EmotionSystem(...)
    trigger = TriggerSystem(...)
    ...

    # 3. 初始化 Tool 适配层
    tools = [
        MemoryTool(memory),
        EmotionTool(emotion),
        TriggerTool(trigger),
        MBTITool(...),
        SceneTool(...),
        LivenessTool(...),
        StateTool(...),
        FeishuTool(...),
        TrendingTool(...),
    ]

    # 4. 构建系统提示
    system_prompt = build_companion_system_prompt(...)

    # 5. 创建 Agent
    agent = Agent(llm_client=llm, system_prompt=system_prompt, tools=tools, ...)

    # 6. 初始化关系阶段
    set_initial_stage(initial_stage)

    # 7. 启动消息路由器
    router = MessageRouter(agent)
    asyncio.create_task(router.run())

    # 8. 启动后台进程
    asyncio.create_task(proactive_loop(router))
    asyncio.create_task(webhook_listener(router, chat_id))
    asyncio.create_task(trending_fetcher())

    # 9. 等待
    await asyncio.Event().wait()
```

### 5.3 后台进程

| 进程 | 频率 | 职责 |
|------|------|------|
| proactive_loop | 每 10 分钟 | 调用 TriggerTool，产生触发意图 |
| webhook_listener | 持续 | 监听飞书 WebSocket，转发用户消息 |
| trending_fetcher | 每天 2-3 次 | 抓取热搜，缓存到 trending.json |
| emotion_residue | session 结束时 | 保存当前情绪状态 |
| anniversary_check | 每天 0 点 | 检查是否有到期的纪念日 |
| time_event_check | 每 1 小时 | 检查时间感知事件是否到期 |

---

## 6. LLM 策略

### 6.1 阶段化方案

| 阶段 | 模型 | 用途 | 成本 |
|------|------|------|------|
| **MVP** | DeepSeek API（支持 COT） | 全部调用 | API 费用 |
| **生产** | 本地 4B/7B 微调模型 | 日常对话（90%+） | 硬件成本 |
| **生产** | DeepSeek API | 高智商场景（矛盾检测、偏好推断） | API 费用 |

### 6.2 MVP 阶段：DeepSeek

- **协议**：OpenAI 兼容（Mini-Agent 的 `openai_client.py` 直接支持）
- **COT 模式**：用于 TriggerTool 两阶段决策、矛盾检测、复杂推理
- **推荐硬件**：Mac Mini 16GB 或同等 Windows 机器（16GB 显存）
- **API base**：通过 `config.yaml` 配置，支持灵活切换

### 6.3 生产阶段：本地 + 云端混合

**LLM Router**（新增）：
```python
class LLMRouter:
    """根据任务复杂度路由到不同模型"""

    def __init__(self, local_model: str, cloud_model: str):
        self.local = LLMClient(api_base="http://localhost:1234/v1", model=local_model)
        self.cloud = LLMClient(api_key="...", model=cloud_model)

    async def simple_generate(self, prompt: str) -> str:
        """日常对话：本地模型"""
        return await self.local.generate(prompt)

    async def complex_reason(self, prompt: str) -> str:
        """高智商场景：云端 API"""
        return await self.cloud.generate(prompt, reasoning=True)  # COT
```

**路由规则**：
| 任务类型 | 模型 | 示例 |
|----------|------|------|
| 日常回复 | 本地 4B/7B | 问候、分享、关心 |
| 情绪表达 | 本地 4B/7B | 想念、撒娇、安慰 |
| 矛盾检测 | DeepSeek API（COT） | 用户前后说法不一致 |
| 偏好推断 | DeepSeek API（COT） | 从事实中推断 L2+ 偏好 |
| 记忆温度计算 | 本地（纯计算，不调 LLM） | — |

### 6.4 微调策略

- **训练集来源**：MVP 阶段 DeepSeek 的对话数据
- **基座模型**：待定（将在 Qwen 小模型 与 DeepSeek 小模型之间测试后选择）
- **风格一致性**：微调基于线上模型输出 → 用户感知不到切换

### 6.5 COT 与活人感

COT 模式在以下场景启用：
1. **TriggerTool 决策** — LLM 推理 pull vs hold_back 的权衡
2. **矛盾追问** — LLM 判断是否值得追问、如何温和地问
3. **记忆闪回** — LLM 判断哪个记忆最适合当前对话

非 COT 场景：
- 日常回复生成
- 情绪表达
- 简单问候/关心

---

## 7. 配置体系

所有可调整参数统一配置，避免硬编码：

| 配置文件 | 内容 | 后续可调 |
|----------|------|----------|
| `triggers.json` | Weibull alpha/beta、HardFilter 参数 | ✅ |
| `emotions.json` | 8 种情绪权重、事件影响映射、昼夜节律参数 | ✅ |
| `scenes.json` | 11+ 场景基础权重、适合 mood/hour | ✅ |
| `relationship.json` | 6 阶段参数（触发频率/表达强度/场景系数/推进条件） | ✅ |
| `mbti_types.json` | 16 种类型画像（或用 mbti_type.py） | ✅ |
| `habits.json` | 个性化习惯配置（语气词/emoji/固定时间） | ✅ |
| `persona.json` | 人物卡（名字、MBTI、特质） | ✅ |

---

## 7. Token 经济性策略

| 策略 | 实现方式 | 节省预估 |
|------|----------|----------|
| 预计算 | 情绪/场景/热搜后台预计算，不占 LLM 推理步骤 | ~30% |
| 缓存 | MBTI 类型、关系阶段、配置数据缓存到 context 注入时 | ~15% |
| 系统提示精简 | 核心规则 + 工具列表 < 2000 tokens | 基础优化 |
| 对话 summarization | Mini-Agent 内置支持，超过 token limit 自动摘要 | 防止溢出 |
| 工具调用精简 | 每个 Tool 返回结构化 JSON，无冗余描述 | ~10% |
| 热搜不实时调用 | 定时缓存替代 LLM 搜索 | ~5% |

---

## 8. 开源模块化设计

### 8.1 模块独立测试

每个 module 可独立运行，不需要 Mini-Agent：

```bash
# 测试记忆模块
uv run python -m companion.modules.memory tests/fixtures/memory_data.json

# 测试情绪模块
uv run python -c "from companion.modules.emotion import get_current_emotion; print(get_current_emotion('user_message'))"
```

### 8.2 接口文档

每个模块的 `__init__.py` 提供清晰的入口：

```python
# companion/modules/memory/__init__.py
"""
记忆系统模块 — 温度检索 + 偏好推断 + 矛盾检测

用法：
    from companion.modules.memory import MemorySystem

    memory = MemorySystem(store_path="...")
    results = memory.search("用户喜欢什么")
    memory.record("用户喜欢吃辣", importance=0.7)
"""

from .fact_store import FactStore
from .preference import PreferenceInfer
from .contradiction import ContradictionDetector

class MemorySystem:
    """记忆系统统一入口"""
    ...
```

### 8.3 可替换设计

每个模块内部实现可替换，只要接口不变：

```
memory/fact_store.py      # 默认实现：JSON + 温度排序
memory/fact_store_vec.py  # 可选实现：向量检索（后续可扩展）

emotion/core.py           # 默认实现：余弦波
emotion/core_ml.py        # 可选实现：ML 模型预测情绪（后续可扩展）
```

### 8.4 开箱即用

```bash
# clone + 配置 + 运行
git clone <repo> ai-companion-ng
cd ai-companion-ng
cp .env.example .env
# 编辑 .env 填入 API key 和飞书凭据
uv sync
uv run python -m companion.scheduler.start_companion --chat-id oc_xxx --initial-stage 2
```

---

## 9. 阶段计划

| Phase | 内容 | 工时 | 验证标准 |
|-------|------|------|----------|
| 0 | 环境搭建 + 目录骨架 | 0.5 天 | Mini-Agent 122 测试通过 |
| 1 | 模块提取 + 梳理优化 | 5 天 | 所有模块独立测试通过 |
| 2 | Tool 适配层集成 | 3 天 | 每个 Tool 独立调用正常 |
| 3 | 运行时搭建 | 2.5 天 | 消息路由 + 主动触发 + 飞书收发 |
| 4 | 验证与测试 | 2 天 | 核心流程端到端通过 |
| 5 | 正式切换 | 3 天 | 新旧并行 3 天，效果对比通过 |
| **合计** | | **16 天** | |

---

**版本**: 1.0
**日期**: 2026-04-30
