/* AI 伴侣 WebUI — 前端逻辑 */

// ── State ──
let ws = null;
let currentConfig = {};
let messages = [];

// ── DOM refs ──
const $ = (s) => document.querySelector(s);
const chatView = document.getElementById('chatView');
const settingsView = document.getElementById('settingsView');
const aboutView = document.getElementById('aboutView');
const msgContainer = document.getElementById('messages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const statusText = document.getElementById('statusText');
const statusDot = document.getElementById('statusDot');

// ── Init ──
async function init() {
  await loadConfig();
  await loadPersonas();
  connectWebSocket();
  addSystemMessage('你好呀～ 我是小美，你的 AI 伴侣。有什么想聊的吗？💕');
  chatInput.focus();
}

// ── View Switching ──
function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  chatView.classList.toggle('hidden', view !== 'chat');
  settingsView.classList.toggle('active', view === 'settings');
  aboutView.classList.toggle('active', view === 'about');

  if (view === 'settings') {
    loadSettingsForm();
    pollFeishuStatus();
    refreshStats();
    if (window._feishuPollTimer) clearInterval(window._feishuPollTimer);
    window._feishuPollTimer = setInterval(pollFeishuStatus, 10000);
  } else {
    if (window._feishuPollTimer) {
      clearInterval(window._feishuPollTimer);
      window._feishuPollTimer = null;
    }
  }

  if (view === 'chat') setTimeout(() => chatInput.focus(), 100);
}

// ── API ──
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    currentConfig = await res.json();
  } catch (e) {
    console.error('Failed to load config', e);
  }
}

async function loadPersonas() {
  try {
    const res = await fetch('/api/personas');
    const data = await res.json();
    const sel = document.getElementById('selPersona');
    sel.innerHTML = data.personas.map(p =>
      `<option value="${p.name}">${p.label}</option>`
    ).join('');
  } catch (e) {
    console.error('Failed to load personas', e);
  }
}

async function saveAllSettings() {
  const body = {
    persona: document.getElementById('selPersona').value,
    mbti: document.getElementById('selMbti').value,
    model: document.getElementById('inputModel').value || 'deepseek-v4-flash',
    api_base: document.getElementById('inputApiBase').value || 'https://api.deepseek.com/v1',
    api_key: document.getElementById('inputApiKey').value || '',
    cloud_price_in: parseFloat(document.getElementById('inputCloudPriceIn').value) || 1.0,
    cloud_price_out: parseFloat(document.getElementById('inputCloudPriceOut').value) || 4.0,
    local_model_enabled: document.getElementById('localModelToggle').checked,
    local_model: document.getElementById('inputLocalModel').value || 'qwen3-4b',
    local_api_base: document.getElementById('inputLocalApiBase').value || 'http://127.0.0.1:1234/v1',
    feishu_enabled: document.getElementById('feishuToggle').checked,
    feishu_app_id: document.getElementById('feishuAppId').value || '',
    feishu_app_secret: document.getElementById('feishuAppSecret').value || '',
    feishu_chat_id: document.getElementById('feishuChatId').value || '',
    budget: parseFloat(document.getElementById('inputBudget').value) || 0,
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showToast('设置已保存，重新连接中…');
      ws?.close();
      setTimeout(() => connectWebSocket(), 300);
      switchView('chat');
    }
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}

async function reloadSession() {
  try {
    await fetch('/api/reload', { method: 'POST' });
    showToast('会话已重建');
    ws?.close();
    setTimeout(() => connectWebSocket(), 300);
  } catch (e) {
    showToast('重建失败: ' + e.message);
  }
}

// ── Token Stats ──
async function refreshStats() {
  try {
    const res = await fetch('/api/token-stats');
    const stats = await res.json();

    document.getElementById('statCalls').textContent = stats.total_calls.toLocaleString();
    document.getElementById('statTokens').textContent = formatBigNum(stats.total_tokens);
    document.getElementById('statCost').textContent = '¥' + stats.total_cost.toFixed(4);
    document.getElementById('statAvg').textContent = stats.total_calls > 0
      ? formatBigNum(stats.avg_tokens_per_call)
      : '—';

    // 预算条
    const budget = currentConfig.budget || 0;
    const bar = document.getElementById('budgetBar');
    const fill = document.getElementById('budgetFill');
    const text = document.getElementById('budgetText');
    if (budget > 0 && stats.total_calls > 0) {
      bar.style.display = '';
      const pct = Math.min(100, (stats.total_cost / budget) * 100);
      fill.style.width = pct + '%';
      fill.className = 'budget-fill' + (pct >= 100 ? ' danger' : pct >= 80 ? ' warn' : '');
      const remaining = budget - stats.total_cost;
      text.textContent = remaining >= 0
        ? `已用 ¥${stats.total_cost.toFixed(2)} / ¥${budget.toFixed(2)}，剩余 ¥${remaining.toFixed(2)}`
        : `⚠️ 已超出预算 ¥${Math.abs(remaining).toFixed(2)}！`;
    } else {
      bar.style.display = 'none';
    }

    // 按模型明细
    const container = document.getElementById('modelBreakdown');
    const models = Object.keys(stats.model_breakdown || {});
    if (models.length === 0) {
      container.innerHTML = '<div class="hint">暂无数据</div>';
    } else {
      container.innerHTML = models.map(m => {
        const mb = stats.model_breakdown[m];
        return `<div class="model-row">
          <span class="name">${m}</span>
          <span class="detail">${mb.calls} 次 · ${formatBigNum(mb.total_tokens)} tokens · ¥${mb.cost.toFixed(4)}</span>
        </div>`;
      }).join('');
    }
  } catch (e) {
    console.error('Failed to load token stats', e);
  }
}

async function resetStats() {
  if (!confirm('确定要清空所有 Token 统计吗？此操作不可撤销。')) return;
  try {
    await fetch('/api/token-reset', { method: 'POST' });
    showToast('统计已清空');
    refreshStats();
  } catch (e) {
    showToast('清空失败: ' + e.message);
  }
}

function formatBigNum(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

// ── Character Card Import ──
document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('fileInput');
  if (fileInput) {
    fileInput.addEventListener('change', function() {
      const nameEl = document.getElementById('fileName');
      const btn = document.getElementById('importBtn');
      if (this.files && this.files.length > 0) {
        nameEl.textContent = this.files[0].name;
        btn.disabled = false;
      } else {
        nameEl.textContent = '未选择文件';
        btn.disabled = true;
      }
    });
  }
});

async function importCharacter() {
  const fileInput = document.getElementById('fileInput');
  if (!fileInput.files || fileInput.files.length === 0) return;

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);

  const btn = document.getElementById('importBtn');
  const originalText = btn.textContent;
  btn.textContent = '导入中…';
  btn.disabled = true;

  try {
    const res = await fetch('/api/import-character', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '导入失败');
    }

    const data = await res.json();
    showToast(`✅ 角色 "${data.persona.label}" 导入成功`);

    await loadPersonas();
    document.getElementById('selPersona').value = data.persona.name;

    fileInput.value = '';
    document.getElementById('fileName').textContent = '未选择文件';
  } catch (e) {
    showToast('❌ ' + e.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

// ── Avatar ──
async function uploadAvatar(role, input) {
  if (!input.files || !input.files[0]) return;

  const file = input.files[0];
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`/api/upload-avatar/${role}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error((await res.json()).detail || '上传失败');
    showToast('头像已更新');
    currentConfig[`has_avatar_${role}`] = true;
    updateAvatarPreview(role);
  } catch (e) {
    showToast('上传失败: ' + e.message);
  }
  input.value = '';
}

async function deleteAvatar(role) {
  try {
    const res = await fetch(`/api/delete-avatar/${role}`, { method: 'POST' });
    if (!res.ok) throw new Error('删除失败');
    showToast('头像已删除');
    currentConfig[`has_avatar_${role}`] = false;
    updateAvatarPreview(role);
  } catch (e) {
    showToast('删除失败: ' + e.message);
  }
}

function updateAvatarPreview(role) {
  const preview = document.getElementById(`${role}AvatarPreview`);
  const delBtn = document.getElementById(`${role}AvatarDeleteBtn`);
  const hasAvatar = currentConfig[`has_avatar_${role}`];
  const cacheBuster = Date.now();

  if (hasAvatar) {
    preview.innerHTML = `<img src="/api/avatar/${role}?t=${cacheBuster}" alt="${role} avatar">`;
    delBtn.style.display = '';
  } else {
    preview.innerHTML = `<span class="avatar-placeholder">${role === 'ai' ? '🤖' : '👤'}</span>`;
    delBtn.style.display = 'none';
  }
}

// ── Feishu Status ──
function updateFeishuStatus(connected) {
  const dot = document.getElementById('feishuStatusDot');
  const text = document.getElementById('feishuStatusText');
  if (connected) {
    dot.style.background = '#22c55e';
    text.textContent = '已连接';
  } else {
    dot.style.background = '#ef4444';
    text.textContent = '未连接';
  }
}

async function pollFeishuStatus() {
  try {
    const res = await fetch('/api/feishu/status');
    const data = await res.json();
    updateFeishuStatus(data.connected);
  } catch (e) {
    // 静默失败，下次轮询
  }
}

// ── Settings Form ──
async function loadSettingsForm() {
  await loadConfig();
  document.getElementById('selMbti').value = currentConfig.mbti || 'ENFP';
  document.getElementById('inputModel').value = currentConfig.model || '';
  document.getElementById('inputApiBase').value = currentConfig.api_base || '';
  document.getElementById('inputApiKey').value = currentConfig.api_key || '';
  document.getElementById('inputCloudPriceIn').value = currentConfig.cloud_price_in || 1.0;
  document.getElementById('inputCloudPriceOut').value = currentConfig.cloud_price_out || 4.0;

  // 本地模型设置
  document.getElementById('localModelToggle').checked = currentConfig.local_model_enabled || false;
  document.getElementById('inputLocalModel').value = currentConfig.local_model || '';
  document.getElementById('inputLocalApiBase').value = currentConfig.local_api_base || '';

  // 飞书设置
  document.getElementById('feishuToggle').checked = currentConfig.feishu_enabled || false;
  document.getElementById('feishuAppId').value = currentConfig.feishu_app_id || '';
  document.getElementById('feishuAppSecret').value = currentConfig.feishu_app_secret || '';
  document.getElementById('feishuChatId').value = currentConfig.feishu_chat_id || '';
  updateFeishuStatus(currentConfig.feishu_connected || false);

  // 预算
  document.getElementById('inputBudget').value = currentConfig.budget || '';

  // 加载头像预览
  updateAvatarPreview('ai');
  updateAvatarPreview('user');

  // 重新加载人格列表并选中当前
  await loadPersonas();
  if (currentConfig.persona) {
    document.getElementById('selPersona').value = currentConfig.persona;
  }
}

// ── WebSocket ──
function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws/chat`;

  if (ws) {
    ws.onclose = null;
    ws.close();
  }

  ws = new WebSocket(url);

  ws.onopen = () => {
    setOnline(true);
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case 'message':
        hideTyping();
        addMessage(data.content, 'ai');
        setOnline(true);
        break;
      case 'status':
        if (data.content === 'thinking') showTyping();
        break;
      case 'proactive':
        hideTyping();
        addMessage(data.content, 'ai');
        break;
      case 'error':
        hideTyping();
        addMessage('😅 ' + data.content, 'ai');
        setOnline(true);
        break;
    }
  };

  ws.onclose = () => {
    setOnline(false);
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    setOnline(false);
  };
}

// ── Chat ──
function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  chatInput.value = '';
  autoResize(chatInput);
  addMessage(text, 'user');
  ws.send(JSON.stringify({ message: text }));
  sendBtn.disabled = true;
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── UI Helpers ──
function addMessage(text, role) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';

  const hasAvatar = currentConfig[`has_avatar_${role}`];
  if (hasAvatar) {
    avatar.innerHTML = `<img src="/api/avatar/${role}?t=${Date.now()}" class="avatar-img">`;
  } else {
    avatar.textContent = role === 'ai' ? '🤖' : '👤';
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;

  div.appendChild(avatar);
  div.appendChild(bubble);
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

function addSystemMessage(text) {
  addMessage(text, 'ai');
}

function showTyping() {
  setOnline(false);
  let existing = document.getElementById('typing-indicator');
  if (existing) return;

  const div = document.createElement('div');
  div.className = 'message ai';
  div.id = 'typing-indicator';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  if (currentConfig.has_avatar_ai) {
    avatar.innerHTML = `<img src="/api/avatar/ai?t=${Date.now()}" class="avatar-img">`;
  } else {
    avatar.textContent = '🤖';
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  div.appendChild(avatar);
  div.appendChild(bubble);
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
  sendBtn.disabled = false;
}

function setOnline(online) {
  statusDot.style.background = online ? '#22c55e' : '#ef4444';
  statusText.textContent = online ? `在线 · ${currentConfig.mbti || 'ENFP'}` : '思考中…';
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Start ──
init();
