# 飞书 Bot 集成设计方案

> AI Companion-ng v2.0 飞书长连接 Bot 接入
> 版本：1.0 | 日期：2026-05-01

---

## 一、架构概述

### 1.1 设计目标

将 AI Companion-ng 通过飞书开放平台的长连接（WebSocket）机器人接入，使用户能在飞书内直接与 AI 伴侣对话。

**关键约束：**
- **飞书长连接**：通过 `lark-oapi` SDK 的 WS Client 订阅事件，无需公网 IP
- **3秒响应窗口**：飞书要求 Bot 在 3 秒内响应，超时会重发消息
- **共享状态**：飞书 Bot 共享 Mini-Agent 和 CompanionRegistry（记忆/情绪/关系状态）
- **WebUI 共存**：Bot 与现有 WebUI 并行运行，不影响原有功能

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────┐
│                  ai-companion-ng                         │
│                                                          │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │   FastAPI Server  │    │   FeishuBot (daemon)     │   │
│  │   (WebUI + WS)    │    │                          │   │
│  │                   │    │  lark.ws.Client          │   │
│  │  /api/config      │    │  ┌──────────────────┐   │   │
│  │  /ws/chat         │    │  │ _on_message()    │   │   │
│  │  ...              │    │  │ → run_coroutine_ │   │   │
│  └──────┬───────────┘    │  │   threadsafe()    │   │   │
│         │                │  └────────┬─────────┘   │   │
│         │                └───────────┼──────────────┘   │
│         ▼                            ▼                  │
│  ┌────────────────────────────────────────────────┐     │
│  │          CompanionRegistry (共享)               │     │
│  │  MemorySystem / EmotionSystem / TriggerEngine  │     │
│  │  RelationshipManager / MBTIAdapter / SceneLib  │     │
│  └────────────────────────────────────────────────┘     │
│                          │                               │
│                          ▼                               │
│  ┌────────────────────────────────────────────────┐     │
│  │          SilentAgentWrapper (共享)              │     │
│  │          (Mini-Agent + Persona)                 │     │
│  └────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 1.3 消息流

```
飞书用户 → 飞书服务器 → WS → FeishuBot._on_message()
                                        │
                          ┌─────────────┴─────────────┐
                          │  立即回复 200 OK (防重发)   │
                          │  await event.ack()         │
                          └─────────────┬─────────────┘
                                        │
                    asyncio.run_coroutine_threadsafe(
                        agent.run(text), main_loop
                    )
                                        │
                          ┌─────────────┴─────────────┐
                          │  Agent 回复完成后           │
                          │  → 通过飞书 API 发送消息     │
                          │  client.im.v1.messages.create│
                          └───────────────────────────┘
```

### 1.4 生命周期

```
FastAPI lifespan.startup
    ↓
FeishuBot.__init__(config, loop)
    ↓
FeishuBot.start() → daemon thread → lark.ws.Client.start()
    ↓
WS 连接建立 → 事件循环监听
    ↓
FastAPI lifespan.shutdown
    ↓
FeishuBot.stop() → daemon thread join
```

---

## 二、模块设计

### 2.1 FeishuBot 类

**文件：** `companion/modules/feishu/bot.py`

```python
class FeishuBot:
    def __init__(self, app_id: str, app_secret: str, loop: asyncio.AbstractEventLoop):
        self._client = None          # lark.ws.Client
        self._agent = None           # SilentAgentWrapper 懒加载
        self._loop = loop            # 主事件循环引用
        self._thread = None          # daemon thread
        self._running = False

    def start(self):
        """启动 daemon thread 运行 lark.ws.Client"""

    def stop(self):
        """关闭 WS 连接，停止线程"""

    def _get_or_create_agent(self) -> SilentAgentWrapper:
        """懒加载 agent（复用全局 CompanionRegistry）"""

    async def _on_message(self, event: Event):
        """处理收到的飞书消息 → 调用 agent → 回复"""

    async def _reply(self, open_id: str, text: str):
        """通过飞书 API 发送文本消息"""
```

**关键设计点：**

1. **线程安全**：`lark.ws.Client` 的 callback 在 SDK 内部线程运行。通过 `asyncio.run_coroutine_threadsafe()` 将 agent 调用调度到主事件循环。

2. **3 秒限制**：`_on_message()` 先调用 `event.ack()` 立即回复飞书服务器，再异步处理 agent 调用。即使 agent 处理超过 3 秒也不会触发重发。

3. **Agent 懒加载**：Bot 首次收到消息时才创建 agent 实例，避免启动时加载开销。agent 创建逻辑复用 `build_companion_agent()`。

4. **配置热更新**：Bot 的配置（App ID / Secret）跟随 WebUI 设置页面的保存操作更新，通过重建 agent 实现。

### 2.2 消息处理

```python
async def _on_message(self, event: Event):
    # 1. 立即 ack 防止飞书重发
    await event.ack()

    # 2. 解析消息内容
    if event.event.message.message_type != "text":
        return  # 暂只支持文本
    text = extract_text(event.event.message.content)

    # 3. 确保 agent 已加载
    agent = self._get_or_create_agent()

    # 4. 调用 agent（在主事件循环执行）
    future = asyncio.run_coroutine_threadsafe(
        agent.run(text), self._loop
    )
    try:
        response = future.result(timeout=30)
    except TimeoutError:
        response = "抱歉，我还在思考… 请稍后再问一遍。"
    except Exception as e:
        response = f"哎呀出错了: {str(e)}"

    # 5. 回复（通过飞书 API）
    await self._reply(event.event.message.chat_id, response)
```

### 2.3 服务端集成

**文件：** `companion/webui/server.py`

```diff
+ from companion.modules.feishu.bot import FeishuBot

  _config = {
      ...
+     "feishu_app_id": "",
+     "feishu_app_secret": "",
+     "feishu_enabled": False,
  }

+ _feishu_bot = None

  @asynccontextmanager
  async def lifespan(app: FastAPI):
+     _start_feishu_bot()
      yield
+     _stop_feishu_bot()
      ...

+ def _start_feishu_bot():
+     global _feishu_bot
+     if not _config.get("feishu_enabled") or not _config.get("feishu_app_id"):
+         return
+     loop = asyncio.get_event_loop()
+     _feishu_bot = FeishuBot(_config["feishu_app_id"], _config["feishu_app_secret"], loop)
+     _feishu_bot.start()

+ def _stop_feishu_bot():
+     global _feishu_bot
+     if _feishu_bot:
+         _feishu_bot.stop()
+         _feishu_bot = None
```

### 2.4 API 端点

WebUI 需要新增飞书配置管理端点：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/config` | 已有，扩展 feishu_app_id / feishu_app_secret / feishu_enabled 字段 |
| GET  | `/api/feishu/status` | 获取飞书 Bot 连接状态（connected / disconnected / disabled） |

### 2.5 前端设置

**文件：** `companion/webui/static/index.html`

在设置页面新增 "飞书 Bot" 区域：
- 启用开关（checkbox/toggle）
- App ID 输入框
- App Secret 输入框（password 类型）
- 状态指示器（已连接 / 未连接 / 已禁用）
- 保存按钮（复用已有保存逻辑）

### 2.6 Bot 启动流程 (daemon thread)

```
FeishuBot.start()
    │
    ├── daemon_thread = threading.Thread(target=_run, daemon=True)
    │
    ▼
    _run():
    │
    ├── Create EventHandler with _on_message
    │
    ├── Create lark.ws.Client(app_id, app_secret, event_handler)
    │
    └── client.start()  # 阻塞，SDK 内部维护 WS 连接
```

---

## 三、依赖

```
lark-oapi>=1.2.0
```

添加到 `requirements.txt` 或项目依赖。

---

## 四、实现计划

### Phase 1: 核心模块（~1h）

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1.1 | `companion/modules/feishu/__init__.py` | 空导出 |
| 1.2 | `companion/modules/feishu/bot.py` | FeishuBot 类（WS client + agent 懒加载 + 消息处理） |
| 1.3 | 更新 `companion/webui/server.py` | lifespan 集成、API 扩展、配置热更新 |

### Phase 2: 前端 UI（~30min）

| 步骤 | 文件 | 内容 |
|------|------|------|
| 2.1 | `companion/webui/static/index.html` | 飞书设置区域（启用/App ID/Secret/状态） |
| 2.2 | `companion/webui/static/js/app.js` | 飞书设置逻辑（保存/状态轮询） |
| 2.3 | `companion/webui/static/css/style.css` | 飞书 UI 样式 |

### Phase 3: 验证（~30min）

| 步骤 | 内容 |
|------|------|
| 3.1 | 启动服务，检查飞书 Bot 连接状态 |
| 3.2 | 飞书内发送消息，确认正常回复 |
| 3.3 | 测试热更新（WebUI 切换设置后重建） |
| 3.4 | 测试断线重连 |

---

## 五、风险与注意事项

### 5.1 3 秒响应窗口

- ✅ `event.ack()` 立即回复飞书服务器，不等待 agent 结果
- ✅ Agent 处理超时也有 fallback 回复
- ⚠️ 飞书可能因网络延迟 `ack` 超时，设置合理超时时间

### 5.2 线程安全

- `lark.ws.Client` 的 callback 在 SDK 内部线程执行
- `asyncio.run_coroutine_threadsafe` 将 agent 调用调度到主事件循环
- 共享数据（CompanionRegistry）受主事件循环保护，无竞态

### 5.3 资源管理

- FeishuBot 随 FastAPI lifespan 启动/停止
- daemon thread 自动随主进程退出终止
- agent 实例懒加载，首次消息到达时创建

### 5.4 配置管理

- App ID / Secret 存在内存配置中（`_config` 字典）
- 重启后需要重新设置（当前无持久化配置）
- 长期方案：将飞书配置加入持久化配置存储

---

## 六、测试策略

| 类型 | 内容 | 方法 |
|------|------|------|
| 单元测试 | FeishuBot._reply 构造正确请求 | mock lark-oapi Client |
| 集成测试 | WS 连接与消息处理流程 | local lark-oapi test server |
| E2E | 真实飞书消息 → agent → 回复 | 手动测试 |
| 压力测试 | 高并发消息下的响应 | 批量发送 + 监控超时 |
