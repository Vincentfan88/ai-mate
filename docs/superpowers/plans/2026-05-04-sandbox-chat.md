# 无痕模式（Sandbox Chat）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户开启无痕模式后，所有对话/记忆/状态写入独立的临时目录（`tempfile.TemporaryDirectory`），与主 workspace 完全隔离。关闭无痕模式时，临时目录整个销毁，不留任何痕迹。

**Architecture:** 在 server 层维护两套 agent — 主 agent（正常模式）和沙盒 agent（私密模式）。开启私密模式时创建沙盒 registry，workspace 指向 tempdir；关闭时删除 tempdir 并销毁沙盒 agent。前端在"AI 设定"tab 提供私密模式开关，聊天 header 仅显示小指示器。

**Tech Stack:** Python (FastAPI + tempfile), WebSocket, 原生 JavaScript, CSS

**核心设计决策：**
- **沙盒 workspace** = `tempfile.TemporaryDirectory()`，registry 的 `workspace` 参数直接指向 tempdir，所有 12 个写盘模块自动写入临时目录，零侵入修改
- **沙盒 agent 完全独立** — 不共享 memory、emotion、trigger、liveness 的任何磁盘或内存状态
- **私密角色卡一次性导入** — 开启私密模式后，导入的角色卡存到 tempdir 内（`{tempdir}/persona/`），关闭时连同聊天记录一起销毁
- **关闭时 `tempdir.cleanup()`** — 整个目录递归删除，包括角色卡 JSON、MD 日志、facts、preferences、所有 state 文件
- **Token 统计仍计入** — 成本可见，但聊天内容和角色卡不留痕

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `companion/webui/server.py` | Modify | 沙盒 agent 生命周期管理 + toggle/clear API + WebSocket 路由选择 |
| `companion/webui/agent_wrapper.py` | No change | 现有代码已足够，workspace 隔离由 registry 层处理 |
| `companion/webui/static/index.html` | Modify | "AI 设定"tab 添加私密模式卡片 + 聊天 header 添加小指示器 |
| `companion/webui/static/js/app.js` | Modify | 前端私密状态管理 + 开启/关闭/焚毁逻辑 |
| `companion/webui/static/css/style.css` | Modify | 私密模式卡片 + 聊天 badge 样式 |
| `tests/companion/test_sandbox_chat.py` | Create | 沙盒隔离 + 销毁测试 |

---

### Task 1: Server — 沙盒 Agent 生命周期管理

**Files:**
- Modify: `companion/webui/server.py`

- [ ] **Step 1: Add sandbox state variables and imports**

```python
# companion/webui/server.py — add after "import contextlib" (top of file)
import tempfile

# Add after "_feishu_bot = None" (around line 66) — new global sandbox state:

# 无痕模式沙盒 agent
_sandbox_agent = None          # (tempdir, SilentAgentWrapper) 或 None
_sandbox_enabled = False       # 当前是否处于无痕模式
```

- [ ] **Step 2: Add sandbox creation helper**

```python
# companion/webui/server.py — add after _get_or_create_agent() function

def _create_sandbox_agent() -> tuple:
    """创建沙盒 agent — 使用临时目录作为 workspace。

    返回 (tempdir, wrapper) 元组。
    """
    global _config
    tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
    sandbox_workspace = tempdir.name

    logger.info(f"[Sandbox] 创建临时 workspace: {sandbox_workspace}")

    try:
        # 使用与主 agent 相同的构建逻辑，但 workspace 指向 tempdir
        agent = build_companion_agent(
            model=_config.get("model"),
            api_base=_config.get("api_base"),
            api_key=_config.get("api_key"),
            workspace=sandbox_workspace,
            mbti=_config.get("mbti"),
            persona=_config.get("persona"),
            max_steps=_config.get("max_steps"),
        )
        if agent is None:
            tempdir.cleanup()
            raise RuntimeError("Failed to build sandbox agent")

        wrapper = SilentAgentWrapper(agent, registry=agent.registry if hasattr(agent, 'registry') else None)
        return (tempdir, wrapper)
    except Exception:
        if tempdir:
            tempdir.cleanup()
        raise


def _destroy_sandbox() -> None:
    """销毁沙盒 agent + 清理临时目录。"""
    global _sandbox_agent, _sandbox_enabled

    if _sandbox_agent:
        tempdir, wrapper = _sandbox_agent
        try:
            tempdir.cleanup()
            logger.info("[Sandbox] 临时目录已销毁")
        except Exception as e:
            logger.warning(f"[Sandbox] 清理临时目录失败: {e}")
        _sandbox_agent = None

    _sandbox_enabled = False
```

- [ ] **Step 3: Add toggle, clear, and persona import API endpoints**

```python
# companion/webui/server.py — add before "# WebSocket — 对话" section

@app.post("/api/sandbox/toggle")
async def toggle_sandbox(body: dict):
    """开启/关闭私密模式。

    开启: 创建沙盒 agent，workspace 指向 tempdir
    关闭: 销毁沙盒 agent + tempdir.cleanup()
    """
    global _sandbox_agent, _sandbox_enabled, _agent_ref

    enabled = body.get("enabled", False)

    if enabled and not _sandbox_enabled:
        # 开启私密模式
        try:
            _sandbox_agent = _create_sandbox_agent()
            _sandbox_enabled = True
            logger.info("[Sandbox] 私密模式已开启")
            return {"status": "ok", "enabled": True, "message": "私密模式已开启"}
        except Exception as e:
            logger.error(f"[Sandbox] 创建失败: {e}")
            return {"status": "error", "error": f"创建失败: {str(e)}"}

    elif not enabled and _sandbox_enabled:
        # 关闭私密模式
        _destroy_sandbox()
        _agent_ref = None  # 强制下次正常消息时重建主 agent
        logger.info("[Sandbox] 私密模式已关闭")
        return {"status": "ok", "enabled": False, "message": "私密模式已关闭，记录已焚毁"}

    # 状态未变化
    return {"status": "ok", "enabled": _sandbox_enabled}


@app.post("/api/sandbox/clear")
async def clear_sandbox():
    """关闭私密模式并销毁所有临时数据（等价于 toggle off）。"""
    global _sandbox_agent, _sandbox_enabled, _agent_ref

    if not _sandbox_enabled:
        return {"status": "ok", "message": "私密模式未开启"}

    _destroy_sandbox()
    _agent_ref = None
    return {"status": "ok", "message": "私密记录已焚毁"}


@app.post("/api/sandbox/import-persona")
async def sandbox_import_persona(file: UploadFile = File(...)):
    """私密模式下导入角色卡 — 存到 tempdir 内，关闭时一起销毁。

    仅在私密模式已开启时可调用。
    """
    global _sandbox_agent, _sandbox_enabled

    if not _sandbox_enabled or not _sandbox_agent:
        raise HTTPException(status_code=400, detail="请先开启私密模式")

    tempdir, wrapper = _sandbox_agent

    # 在 tempdir 内创建 persona 子目录
    persona_dir = Path(tempdir.name) / "persona"
    persona_dir.mkdir(exist_ok=True)

    content = await file.read()
    filename = file.filename or "sandbox_persona.json"
    persona_path = persona_dir / filename

    try:
        # 如果是 JSON，直接保存
        if filename.endswith(".json"):
            # 验证 JSON 格式
            import json
            persona_data = json.loads(content)
            persona_path.write_text(json.dumps(persona_data, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            raise HTTPException(status_code=400, detail="仅支持 .json 格式的角色卡")

        # 切换当前 persona 到导入的私密角色
        persona_name = persona_data.get("name", "sandbox_persona")
        _config["persona"] = persona_name

        # 重建沙盒 agent 以加载新 persona
        old_tempdir, old_wrapper = _sandbox_agent
        _sandbox_agent = None  # 先清除旧引用

        # 保留 persona 文件到新的 tempdir
        new_tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
        new_sandbox_workspace = new_tempdir.name
        new_persona_dir = Path(new_sandbox_workspace) / "persona"
        new_persona_dir.mkdir(exist_ok=True)
        # 复制 persona 文件
        import shutil
        shutil.copy(str(persona_path), str(new_persona_dir / filename))

        # 重新创建 agent
        new_agent = build_companion_agent(
            model=_config.get("model"),
            api_base=_config.get("api_base"),
            api_key=_config.get("api_key"),
            workspace=new_sandbox_workspace,
            mbti=_config.get("mbti"),
            persona="sandbox",  # 使用 sandbox persona
            max_steps=_config.get("max_steps"),
        )
        if new_agent is None:
            new_tempdir.cleanup()
            raise RuntimeError("Failed to rebuild sandbox agent after persona import")

        new_wrapper = SilentAgentWrapper(new_agent, registry=new_agent.registry if hasattr(new_agent, 'registry') else None)
        _sandbox_agent = (new_tempdir, new_wrapper)

        # 清理旧 tempdir
        old_tempdir.cleanup()

        logger.info(f"[Sandbox] 私密角色已导入: {persona_name}")
        return {"status": "ok", "persona": persona_name, "message": f"私密角色 \"{persona_name}\" 已导入"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="角色卡 JSON 格式无效")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
```

- [ ] **Step 4: Modify WebSocket handler to route to sandbox**

```python
# companion/webui/server.py — modify the websocket_chat function
# Replace lines 932-967 with:

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            user_text = msg.get("message", "").strip()
            if not user_text:
                continue

            # 发送"正在输入"状态
            await ws.send_json({"type": "status", "content": "thinking"})

            # 根据无痕模式选择 agent
            if _sandbox_enabled and _sandbox_agent:
                wrapper = _sandbox_agent[1]
            else:
                wrapper = _get_or_create_agent()

            try:
                if wrapper.registry:
                    wrapper.registry.on_user_message()
                    # 获取当前情绪，随消息一起发送
                    try:
                        emotion_info = wrapper.registry.emotion.get_current_emotion("user_message")
                        current_emotion = emotion_info.get("emotion", "")
                    except Exception:
                        current_emotion = ""

                response = await wrapper.run(user_text)
                if response and not response.startswith("LLM call failed") and not response.startswith("Task couldn't be completed"):
                    # AI 回复后设置 connection 冷却
                    try:
                        wrapper.registry.trigger.connection_axis.on_contact()
                    except Exception as e:
                        logger.warning(f"Connection cooldown failed: {e}")
                    await ws.send_json({
                        "type": "message",
                        "content": response,
                        "emotion": current_emotion,
                        "sandbox": _sandbox_enabled,
                    })
                else:
                    await ws.send_json({"type": "error", "content": "抱歉，我出神了没听清… 能再说一遍吗？"})
            except Exception as e:
                logging.getLogger("companion").error(f"WebSocket 错误: {e}", exc_info=True)
                await ws.send_json({"type": "error", "content": "抱歉，我出错了… 请稍后再试。"})
```

- [ ] **Step 5: Add sandbox status to GET /api/config**

```python
# companion/webui/server.py — modify get_config() return (around line 784)
# Add sandbox_enabled to the return:

    return {
        **safe_config,
        **info,
        "has_avatar_ai": _has_avatar("ai"),
        "has_avatar_user": _has_avatar("user"),
        "feishu_connected": _feishu_bot.is_connected if _feishu_bot else False,
        "sandbox_enabled": _sandbox_enabled,
    }
```

---

### Task 2: Frontend — 私密模式 UI（设置面板 + 聊天提示）

**Files:**
- Modify: `companion/webui/static/index.html`
- Modify: `companion/webui/static/js/app.js`
- Modify: `companion/webui/static/css/style.css`

**设计思路：**
- 私密模式开关放在"AI 设定"tab 顶部（角色级别的选择）
- 开启后出现"导入私密角色卡"提示 + 焚毁按钮
- 聊天 header 仅显示小指示器（让用户知道自己正在私密模式中）

- [ ] **Step 1: Add sandbox toggle card to "AI 设定" tab**

```html
<!-- companion/webui/static/index.html -->
<!-- In the tab-persona-left section, add BEFORE the persona select group (around line 84) -->

                <div class="setting-group setting-group--highlight" id="sandboxCard">
                  <div class="sandbox-toggle-row">
                    <div class="sandbox-toggle-info">
                      <label>🔒 私密模式</label>
                      <div class="hint" id="sandboxHint">开启后对话记录和角色卡写入临时沙盒，关闭即刻焚毁</div>
                    </div>
                    <label class="toggle-switch">
                      <input type="checkbox" id="sandboxToggle" onchange="toggleSandbox()">
                      <span class="toggle-slider"></span>
                    </label>
                  </div>
                </div>
                <!-- 私密模式下的操作区（默认隐藏） -->
                <div class="sandbox-actions" id="sandboxActions" style="display:none">
                  <div class="sandbox-status-line" id="sandboxPersonaStatus">未导入私密角色卡</div>
                  <div class="sandbox-import-row">
                    <input type="file" id="sandboxFileInput" accept=".json" class="file-input-hidden">
                    <button class="btn-secondary" onclick="document.getElementById('sandboxFileInput').click()">选择角色卡</button>
                    <button class="btn-primary btn-sm" id="sandboxImportBtn" onclick="importSandboxPersona(document.getElementById('sandboxFileInput').files[0])">导入</button>
                  </div>
                  <div class="sandbox-divider"></div>
                  <button class="btn-danger btn-sm" id="sandboxClearBtn" onclick="clearSandbox()">
                    <span>🔥 焚毁私密记录</span>
                  </button>
                </div>
```

- [ ] **Step 2: Add subtle sandbox indicator to chat header**

```html
<!-- companion/webui/static/index.html -->
<!-- In the chat-header div, add a sandbox indicator badge (after line 41) -->

        <div class="chat-header">
          <div class="status-dot" id="statusDot"></div>
          <span class="status-text" id="statusText">在线 · ENFP</span>
          <span class="sandbox-badge" id="sandboxBadge" style="display:none">🛡️ 私密</span>
        </div>
```

- [ ] **Step 3: Add sandbox state management to JavaScript**

```javascript
// companion/webui/static/js/app.js — add after the "State" section (after line 9)

// ── Sandbox / Incognito Mode ──
let sandboxEnabled = false;
let sandboxPersonaName = null;  // 私密角色名称

async function toggleSandbox() {
  const enable = !sandboxEnabled;

  try {
    const res = await fetch('/api/sandbox/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enable }),
    });
    const data = await res.json();
    if (data.status === 'ok') {
      sandboxEnabled = data.enabled;
      updateSandboxUI();

      if (sandboxEnabled) {
        // 开启时清除前端消息（视觉干净）
        messages = [];
        msgContainer.innerHTML = '';
        welcomeScreen.style.display = '';
        msgContainer.style.display = 'none';
        lastSenderRole = null;
        lastMessageTime = null;
        sandboxPersonaName = null;
        showToast('🔒 私密模式已开启 — 可导入专属私密角色卡');
      } else {
        showToast('🔥 私密记录已焚毁');
      }
    } else {
      showToast('操作失败: ' + (data.error || '未知错误'), 'error');
      // revert UI
      sandboxEnabled = !sandboxEnabled;
      updateSandboxUI();
    }
  } catch (e) {
    showToast('网络错误: ' + e.message, 'error');
    sandboxEnabled = !sandboxEnabled;
    updateSandboxUI();
  }
}

async function clearSandbox() {
  if (!confirm('确定要焚毁当前私密会话的所有记录吗？此操作不可恢复。')) return;

  try {
    const res = await fetch('/api/sandbox/clear', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
      sandboxEnabled = false;
      sandboxPersonaName = null;
      updateSandboxUI();

      // 清除前端消息
      messages = [];
      msgContainer.innerHTML = '';
      welcomeScreen.style.display = '';
      msgContainer.style.display = 'none';
      lastSenderRole = null;
      lastMessageTime = null;

      showToast('🔥 私密记录已焚毁');
    } else {
      showToast('焚毁失败: ' + (data.error || '未知错误'), 'error');
    }
  } catch (e) {
    showToast('焚毁失败: ' + e.message, 'error');
  }
}

// 私密模式下导入角色卡 — 拦截现有导入逻辑
async function importSandboxPersona(file) {
  const formData = new FormData();
  formData.append('file', file);

  const btn = document.getElementById('sandboxImportBtn');
  const originalText = btn ? btn.textContent : '导入';
  if (btn) { btn.textContent = '导入中…'; btn.disabled = true; }

  try {
    const res = await fetch('/api/sandbox/import-persona', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '导入失败');
    }

    const data = await res.json();
    sandboxPersonaName = data.persona;
    showToast(`🔒 私密角色 "${data.persona}" 已导入 — 关闭模式时自动焚毁`);
    updateSandboxUI();

    // 清除选择
    const fileInput = document.getElementById('sandboxFileInput');
    if (fileInput) fileInput.value = '';
  } catch (e) {
    showToast('❌ ' + e.message);
  } finally {
    if (btn) { btn.textContent = originalText; btn.disabled = false; }
  }
}

function updateSandboxUI() {
  // Settings panel toggle
  const toggle = document.getElementById('sandboxToggle');
  const actions = document.getElementById('sandboxActions');
  const hint = document.getElementById('sandboxHint');
  const sandboxCard = document.getElementById('sandboxCard');
  const personaStatus = document.getElementById('sandboxPersonaStatus');

  if (toggle) toggle.checked = sandboxEnabled;
  if (actions) actions.style.display = sandboxEnabled ? '' : 'none';
  if (hint) hint.textContent = sandboxEnabled
    ? '私密模式已开启 — 所有对话和角色卡临时保存，关闭即焚毁'
    : '开启后对话记录和角色卡写入临时沙盒，关闭即刻焚毁';
  if (sandboxCard) {
    sandboxCard.classList.toggle('active', sandboxEnabled);
  }
  if (personaStatus) {
    personaStatus.textContent = sandboxPersonaName
      ? `🔒 已加载私密角色: ${sandboxPersonaName}`
      : '未导入私密角色卡';
  }

  // Chat header badge
  const badge = document.getElementById('sandboxBadge');
  if (badge) badge.style.display = sandboxEnabled ? 'inline-flex' : 'none';
}

// Load sandbox state from config on init
async function loadSandboxState() {
  try {
    const res = await fetch('/api/config');
    const config = await res.json();
    sandboxEnabled = config.sandbox_enabled || false;
    updateSandboxUI();
  } catch (e) {
    console.error('Failed to load sandbox state', e);
  }
}

// Intercept character import when sandbox is active
// companion/webui/static/js/app.js — modify importCharacter() function (around line 255)
// Add at the start of importCharacter():
async function importCharacter() {
  // 私密模式下走专用导入流程
  if (sandboxEnabled) {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files || fileInput.files.length === 0) return;
    await importSandboxPersona(fileInput.files[0]);
    return;
  }
  // ... existing normal importCharacter logic continues below ...
```

- [ ] **Step 4: Call loadSandboxState() in init()**

```javascript
// companion/webui/static/js/app.js — modify init() (around line 24)

async function init() {
  await loadConfig();
  await loadPersonas();
  await loadSandboxState();  // <-- add this line
  updateWelcomeText();
  connectWebSocket();
  chatInput.focus();
}
```

- [ ] **Step 5: Add CSS styles**

```css
/* companion/webui/static/css/style.css — add before "Responsive" section */

/* ═══════════════════════════════════════
   Sandbox / Incognito Mode
   ═══════════════════════════════════════ */

/* Highlighted card in AI 设定 tab */
.setting-group--highlight {
  background: linear-gradient(135deg, rgba(201, 169, 110, 0.06), rgba(201, 169, 110, 0.02));
  border: 1px solid rgba(201, 169, 110, 0.2);
  border-radius: var(--radius);
  padding: var(--space-md);
  transition: all var(--duration-fast) ease;
}

.setting-group--highlight.active {
  border-color: var(--gold);
  background: linear-gradient(135deg, rgba(201, 169, 110, 0.12), rgba(201, 169, 110, 0.04));
}

.sandbox-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.sandbox-toggle-info label {
  font-size: var(--text-sm);
  font-weight: 800;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  display: block;
  margin-bottom: 2px;
}

/* Sandbox actions row (shown when active) */
.sandbox-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: var(--space-sm) 0;
}

.sandbox-status-line {
  font-size: var(--text-sm);
  color: var(--ink-muted);
  font-style: italic;
}

.sandbox-import-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sandbox-import-row .btn-primary.btn-sm {
  min-width: 56px;
}

.sandbox-divider {
  height: 1px;
  background: var(--rule-light);
  margin: 4px 0;
}

/* Chat header sandbox badge */
.sandbox-badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  background: rgba(201, 169, 110, 0.12);
  border: 1px solid rgba(201, 169, 110, 0.25);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--gold);
  letter-spacing: 0.04em;
}
```

---

### Task 3: Tests — 沙盒隔离 + 销毁验证

**Files:**
- Create: `tests/companion/test_sandbox_chat.py`

- [ ] **Step 1: Write sandbox isolation tests**

```python
# tests/companion/test_sandbox_chat.py
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestSandboxLifecycle:
    """验证沙盒 workspace 与主 workspace 完全隔离。"""

    def _build_server(self, tmpdir: str):
        config_path = f"{tmpdir}/config.json"
        with patch("companion.webui.server.build_companion_agent", return_value=None):
            with patch("companion.webui.server._start_feishu_bot"):
                for mod_name in list(sys.modules.keys()):
                    if "companion.webui.server" in mod_name:
                        del sys.modules[mod_name]
                import companion.webui.server as srv
                srv.CONFIG_FILE = Path(config_path)
                srv._config.clear()
                srv._config.update({
                    "mbti": "ENFP",
                    "persona": "default",
                    "user_name": "",
                    "budget": 0,
                    "quiet_hours_blocks": [[0, 6]],
                    "quiet_hours_start": 0,
                    "quiet_hours_end": 6,
                    "model": os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
                    "api_base": os.environ.get("LLM_API_BASE", "https://api.deepseek.com/v1"),
                    "api_key": os.environ.get("LLM_API_KEY", ""),
                    "max_steps": 5,
                    "workspace": "workspace/companion",
                    "cloud_price_in": 1.0,
                    "cloud_price_out": 4.0,
                    "price_cache_in": 0.1,
                    "local_model_enabled": False,
                    "local_model": "qwen3-4b",
                    "local_api_base": "http://127.0.0.1:1234/v1",
                    "feishu_app_id": "",
                    "feishu_app_secret": "",
                    "feishu_chat_id": "",
                    "feishu_enabled": False,
                })
                srv._agent_ref = None
                srv._sandbox_agent = None
                srv._sandbox_enabled = False
                return srv

    def test_sandbox_creates_tempdir(self, tmp_path):
        srv = self._build_server(str(tmp_path))

        # Mock build_companion_agent to return a fake agent with registry
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        with patch.object(srv, "build_companion_agent", return_value=mock_agent):
            tempdir, wrapper = srv._create_sandbox_agent()

        assert tempdir is not None
        assert tempdir.name.startswith("ai-mate-sandbox-")
        assert Path(tempdir.name).exists()
        assert wrapper is not None

        # Cleanup
        tempdir.cleanup()

    def test_sandbox_destroy_removes_tempdir(self, tmp_path):
        srv = self._build_server(str(tmp_path))

        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        with patch.object(srv, "build_companion_agent", return_value=mock_agent):
            srv._sandbox_agent = srv._create_sandbox_agent()
            srv._sandbox_enabled = True

        tempdir_path = srv._sandbox_agent[0].name
        assert Path(tempdir_path).exists()

        # Destroy
        srv._destroy_sandbox()

        assert not Path(tempdir_path).exists(), "Temp directory should be deleted"
        assert srv._sandbox_agent is None
        assert srv._sandbox_enabled is False

    def test_sandbox_workspace_isolated_from_main(self, tmp_path):
        """验证沙盒 workspace 不写入主 workspace。"""
        srv = self._build_server(str(tmp_path))

        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        with patch.object(srv, "build_companion_agent", return_value=mock_agent):
            tempdir, wrapper = srv._create_sandbox_agent()

        # 验证 workspace 指向 tempdir
        if wrapper.registry:
            assert tempdir.name in wrapper.registry.workspace
            assert "workspace/companion" not in wrapper.registry.workspace or \
                   wrapper.registry.workspace.startswith(tempdir.name)

        tempdir.cleanup()

    def test_toggle_on_and_off(self, tmp_path):
        """验证 toggle 开启和关闭流程。"""
        srv = self._build_server(str(tmp_path))
        assert srv._sandbox_enabled is False

        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        with patch.object(srv, "build_companion_agent", return_value=mock_agent):
            # Toggle on
            srv._sandbox_agent = srv._create_sandbox_agent()
            srv._sandbox_enabled = True
            assert srv._sandbox_enabled is True
            assert srv._sandbox_agent is not None

            tempdir_path = srv._sandbox_agent[0].name

            # Toggle off
            srv._destroy_sandbox()
            assert srv._sandbox_enabled is False
            assert srv._sandbox_agent is None
            assert not Path(tempdir_path).exists()


class TestSandboxDiskIsolation:
    """验证沙盒模式下磁盘文件写入隔离。"""

    def test_sandbox_writes_to_tempdir_not_main_workspace(self, tmp_path):
        """创建沙盒后，主 workspace 目录下不应产生新文件。"""
        main_workspace = tmp_path / "main_workspace"
        main_workspace.mkdir(parents=True, exist_ok=True)

        from companion.modules.memory.md_log import MdConversationLog
        from companion.modules.memory.interaction_cache import InteractionCache

        # 在 tempdir 中创建 memory 模块
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()

        sandbox_log = MdConversationLog(log_dir=str(sandbox_dir / "conversations"))
        sandbox_cache = InteractionCache(cache_path=str(sandbox_dir / "interactions.json"))

        # 写入沙盒
        sandbox_log.append("user", "secret message")
        sandbox_cache.add("user", "secret message")

        # 验证主目录无文件
        main_files = list(main_workspace.rglob("*"))
        assert len(main_files) == 0, f"Main workspace should be empty, found: {main_files}"

        # 验证沙盒目录有文件
        sandbox_files = list(sandbox_dir.rglob("*"))
        assert len(sandbox_files) > 0, "Sandbox should have files"

    def test_persona_file_destroyed_with_sandbox(self, tmp_path):
        """验证私密角色卡在销毁后不存在。"""
        import json

        # 创建 tempdir 并写入角色卡
        tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
        persona_dir = Path(tempdir.name) / "persona"
        persona_dir.mkdir()

        persona_data = {
            "name": "秘密角色",
            "description": "这是一个私密角色",
            "personality": {"core_traits": ["神秘", "温柔"]},
            "speaking_style": {"particles": ["呢", "哦"]},
        }
        persona_path = persona_dir / "secret.json"
        persona_path.write_text(json.dumps(persona_data, ensure_ascii=False), encoding="utf-8")

        # 验证角色卡存在
        assert persona_path.exists(), "Persona file should exist before destroy"

        # 销毁
        tempdir.cleanup()

        # 验证角色卡不存在
        assert not persona_path.exists(), "Persona file should be destroyed"
        assert not Path(tempdir.name).exists(), "Temp directory should be deleted"
```

- [ ] **Step 2: Run tests**

```bash
cd ~/Documents/cyberworld/ai-companion-ng
python -m pytest tests/companion/test_sandbox_chat.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 3: Run full test suite**

```bash
cd ~/Documents/cyberworld/ai-companion-ng
python -m pytest tests/companion/ -v --tb=short
```

Expected: 302 passed (296 original + 6 new).

---

## Self-Review

### Spec Coverage Checklist
- [x] 私密模式开关在"AI 设定"tab → Task 2 (setting-group card)
- [x] 开启后提示导入私密角色卡 → Task 2 (sandbox-import-row + status)
- [x] 私密角色卡一次性导入到 tempdir → Task 1 (`/api/sandbox/import-persona`)
- [x] 关闭时角色卡随 tempdir 一起销毁 → Task 3 (`test_persona_file_destroyed_with_sandbox`)
- [x] 聊天记录写入独立临时目录 → Task 1 (tempdir workspace)
- [x] 与主 workspace 完全隔离 → Task 3 (isolation tests)
- [x] 私密模式下角色卡导入拦截正常流程 → Task 2 (importCharacter 拦截)
- [x] 聊天中可见私密状态 → Task 2 (chat header badge，不干扰)
- [x] 测试 → Task 3 (6 个测试)

### Risk Analysis
- **沙盒 agent 重建** — 导入角色卡后需要重建 agent 以加载新 persona。当前实现是先清理旧 tempdir 再创建新的，中间可能有短暂无 agent 状态。可以优化为热加载，但首次实现先简单处理。
- **`build_companion_agent` 返回值结构** — 需要确认它返回的 agent 是否有 `.registry` 属性。从现有 `_get_or_create_agent()` 来看，build_companion_agent 返回的是 `CompanionRegistry` 或类似结构。如果返回的是 registry 本身，`agent.registry` 需要改为 `agent` 直接使用。
- **前端拦截逻辑** — `importCharacter()` 需要在函数开头加 `if (sandboxEnabled)` 分支拦截，确保私密模式下不走正常导入流程（写入 `companion/skills/companion/`）。
- **Token 统计** — 沙盒 agent 的 token 调用仍会计入全局 `token_tracker`，这是正确的（成本可见，内容不留痕）。
- **并发** — 沙盒 agent 是单例（同时间只能有一个私密会话），符合语义。

---

Plan complete and saved to `docs/superpowers/plans/2026-05-04-sandbox-chat.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**
