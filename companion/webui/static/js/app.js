/* AI 伙伴 WebUI — 前端逻辑 */

// ── State ──
let ws = null;
let currentConfig = {};
let messages = [];
let messageCount = 0;
let currentEmotion = '';  // AI current emotion for status bar
let currentHmmState = '';  // HMM state for status bar

// ── DOM refs ──
const $ = (s) => document.querySelector(s);
const chatView = document.getElementById('chatView');
const diaryView = document.getElementById('diaryView');
const settingsView = document.getElementById('settingsView');
const aboutView = document.getElementById('aboutView');
const msgContainer = document.getElementById('messages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const statusText = document.getElementById('statusText');
const statusDot = document.getElementById('statusDot');
const welcomeScreen = document.getElementById('welcomeScreen');

// ── Init ──
async function init() {
  await loadConfig();
  await loadPersonas();
  updateWelcomeText();
  connectWebSocket();
  chatInput.focus();
}

function updateWelcomeText() {
  const name = currentConfig.persona || 'default';
  const personas = {
    'default': { title: 'Hi there', text: '想聊什么都可以，我一直在这儿～' },
  };
  const info = personas[name] || personas['default'];
  document.getElementById('welcomeTitle').textContent = info.title;
  document.getElementById('welcomeText').textContent = info.text;
}

// ── Mobile sidebar ──
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  sidebar.classList.toggle('open');
  overlay.classList.toggle('show');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('show');
}

// ── View Switching ──
function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  chatView.classList.toggle('hidden', view !== 'chat');
  if (diaryView) diaryView.classList.toggle('active', view === 'diary');
  settingsView.classList.toggle('active', view === 'settings');
  aboutView.classList.toggle('active', view === 'about');

  if (view === 'diary') {
    loadDiary();
  }

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

  // Close mobile sidebar on navigation
  closeSidebar();
}

// ── Tab Switching ──
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.tab === tabId)
  );
  document.querySelectorAll('.tab-content').forEach(content =>
    content.classList.toggle('active', content.id === tabId)
  );
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
    cloud_price_in: parseFloat(document.getElementById('inputPriceIn').value) || 1.0,
    cloud_price_out: parseFloat(document.getElementById('inputPriceOut').value) || 4.0,
    price_cache_in: parseFloat(document.getElementById('inputPriceCache').value) || 0.1,
    user_name: document.getElementById('inputUserName').value || '',
    local_model_enabled: document.getElementById('localModelToggle').checked,
    local_model: document.getElementById('inputLocalModel').value || 'qwen3-4b',
    local_api_base: document.getElementById('inputLocalApiBase').value || 'http://127.0.0.1:1234/v1',
    feishu_enabled: document.getElementById('feishuToggle').checked,
    feishu_app_id: document.getElementById('feishuAppId').value || '',
    feishu_app_secret: document.getElementById('feishuAppSecret').value || '',
    feishu_chat_id: document.getElementById('feishuChatId').value || '',
    budget: parseFloat(document.getElementById('inputBudget').value) || 0,
    quiet_hours_blocks: quietBlocks.map(b => ({ start: b.start, end: b.end })),
    // 兼容旧版字段
    quiet_hours_start: quietBlocks.length > 0 ? quietBlocks[0].start : 0,
    quiet_hours_end: quietBlocks.length > 0 ? quietBlocks[0].end : 6,
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
    document.getElementById('statCacheRate').textContent = stats.cache_hit_rate != null
      ? (stats.cache_hit_rate * 100).toFixed(1) + '%'
      : '—';

    // 预算条 — 按本月
    const budget = currentConfig.budget || 0;
    const bar = document.getElementById('budgetBar');
    const fill = document.getElementById('budgetFill');
    const text = document.getElementById('budgetText');
    const monthLabel = stats.current_month || '';
    if (budget > 0 && stats.total_calls > 0) {
      bar.style.display = '';
      const pct = Math.min(100, (stats.total_cost / budget) * 100);
      fill.style.width = pct + '%';
      fill.className = 'budget-fill' + (pct >= 100 ? ' danger' : pct >= 80 ? ' warn' : '');
      const remaining = budget - stats.total_cost;
      const dailyAvg = stats.days_elapsed > 0 ? (stats.total_cost / stats.days_elapsed).toFixed(2) : '—';
      text.textContent = `${monthLabel} 已用 ¥${stats.total_cost.toFixed(2)} / ¥${budget.toFixed(2)}` +
        (remaining >= 0 ? `，剩余 ¥${remaining.toFixed(2)}` : `，⚠️ 超出 ¥${Math.abs(remaining).toFixed(2)}！`) +
        ` · 日均 ¥${dailyAvg}`;
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
    showToast(`角色 "${data.persona.label}" 导入成功`);

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
    preview.innerHTML = `<span class="avatar-placeholder">${role === 'ai' ? '✨' : '👤'}</span>`;
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
let quietBlocks = [];

function renderQuietBlocks() {
  const container = document.getElementById('quietBlocks');
  if (!container) return;
  container.innerHTML = quietBlocks.map((block, i) =>
    `<div class="quiet-block">
      <input type="number" value="${block.start}" min="0" max="23" step="1"
        onchange="updateBlock(${i}, 'start', this.value)">
      <span class="inline-label">点 至</span>
      <input type="number" value="${block.end}" min="0" max="23" step="1"
        onchange="updateBlock(${i}, 'end', this.value)">
      <span class="inline-label">点</span>
      <button class="remove-block-btn" onclick="removeBlock(${i})">删除</button>
    </div>`
  ).join('');
}

function addQuietBlock() {
  quietBlocks.push({ start: 9, end: 12 });
  renderQuietBlocks();
}

function removeBlock(index) {
  quietBlocks.splice(index, 1);
  renderQuietBlocks();
}

function updateBlock(index, field, value) {
  quietBlocks[index][field] = parseInt(value) || 0;
}

async function loadSettingsForm() {
  await loadConfig();
  document.getElementById('selMbti').value = currentConfig.mbti || 'ENFP';
  document.getElementById('inputModel').value = currentConfig.model || '';
  document.getElementById('inputApiBase').value = currentConfig.api_base || '';
  document.getElementById('inputApiKey').value = currentConfig.api_key || '';
  document.getElementById('inputPriceIn').value = currentConfig.cloud_price_in || 1.0;
  document.getElementById('inputPriceOut').value = currentConfig.cloud_price_out || 4.0;
  document.getElementById('inputPriceCache').value = currentConfig.price_cache_in || 0.1;
  document.getElementById('inputUserName').value = currentConfig.user_name || '';

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

  // 免打扰时段（新版多段）
  const blocks = currentConfig.quiet_hours_blocks;
  if (blocks && Array.isArray(blocks) && blocks.length > 0) {
    quietBlocks = blocks.map(b => ({ start: b[0], end: b[1] }));
  } else {
    // 兼容旧版单段字段
    quietBlocks = [{
      start: currentConfig.quiet_hours_start ?? 0,
      end: currentConfig.quiet_hours_end ?? 6,
    }];
  }
  renderQuietBlocks();

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
        // If the server sent emotion/state info, update status
        if (data.emotion) {
          currentEmotion = data.emotion;
          updateStatusDisplay();
        }
        streamMessage(data.content, 'ai');
        setOnline(true);
        break;
      case 'status':
        if (data.content === 'thinking') showTyping();
        break;
      case 'proactive':
        hideTyping();
        if (data.emotion) currentEmotion = data.emotion;
        streamMessage(data.content, 'ai');
        break;
      case 'error':
        hideTyping();
        addMessage('😅 ' + data.content, 'ai');
        setOnline(true);
        break;
      case 'state':
        // Background state update from server
        if (data.emotion) currentEmotion = data.emotion;
        if (data.hmm) currentHmmState = data.hmm;
        updateStatusDisplay();
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
function sendSuggestion(text) {
  chatInput.value = text;
  sendMessage();
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  chatInput.value = '';
  autoResize(chatInput);
  addMessage(text, 'user');

  // Set loading state
  sendBtn.disabled = true;
  sendBtn.classList.add('loading');

  ws.send(JSON.stringify({ message: text }));
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

function hideWelcome() {
  if (welcomeScreen) {
    welcomeScreen.style.display = 'none';
  }
  if (msgContainer) {
    msgContainer.style.display = '';
  }
}

// ── Message group tracking ──
let lastSenderRole = null;
let lastMessageTime = null;
const GROUP_GAP_MS = 60000; // 1 min gap = new group

// ── Streaming message (typing effect) ──
function streamMessage(text, role) {
  messageCount++;
  hideWelcome();

  const isGrouped = (role === lastSenderRole) &&
    lastMessageTime && (Date.now() - lastMessageTime) < GROUP_GAP_MS;

  const div = document.createElement('div');
  div.className = `message ${role}` + (isGrouped ? ' grouped' : '');

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  const hasAvatar = currentConfig[`has_avatar_${role}`];
  if (hasAvatar) {
    avatar.innerHTML = `<img src="/api/avatar/${role}?t=${Date.now()}" class="avatar-img">`;
  } else {
    avatar.textContent = role === 'ai' ? '✨' : '👤';
  }

  const content = document.createElement('div');
  content.className = 'message-content';

  if (!isGrouped) {
    const sender = document.createElement('div');
    sender.className = 'message-sender';
    sender.textContent = getSenderName(role);
    content.appendChild(sender);
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble streaming';
  content.appendChild(bubble);

  const time = document.createElement('div');
  time.className = 'message-time';
  time.textContent = formatTime(new Date());
  content.appendChild(time);

  div.appendChild(avatar);
  div.appendChild(content);
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;

  // Typing animation with realistic rhythm
  const speed = getTypingSpeed(text.length);
  typeText(bubble, text, speed, () => {
    bubble.classList.remove('streaming');
    // Parse action text after typing completes
    parseActionText(bubble);
    // Add emotion tag for AI messages
    if (role === 'ai' && currentEmotion) {
      const tag = document.createElement('div');
      tag.className = 'emotion-tag';
      tag.textContent = currentEmotion;
      bubble.parentNode.appendChild(tag);
    }
  });

  lastSenderRole = role;
  lastMessageTime = Date.now();
}

function getTypingSpeed(textLength) {
  // Variable speed: ~15-30 chars/sec, slower for longer text
  if (textLength < 20) return 40;  // ~25 chars/sec
  if (textLength < 50) return 45;  // ~22 chars/sec
  if (textLength < 100) return 55; // ~18 chars/sec
  return 65; // ~15 chars/sec
}

function typeText(element, text, delay, callback) {
  let i = 0;
  // Handle punctuation pauses
  const pauseChars = '。！？，、';
  function type() {
    if (i < text.length) {
      element.textContent += text[i];
      i++;
      let currentDelay = delay;
      // Pause at punctuation for natural rhythm
      if (pauseChars.includes(text[i - 1])) {
        currentDelay *= 3;
      }
      // Also pause at periods and commas (English)
      if ('.!?,'.includes(text[i - 1])) {
        currentDelay *= 2;
      }
      element.closest('.messages')?.scrollTo({
        top: element.closest('.messages').scrollHeight,
        behavior: 'smooth'
      });
      setTimeout(type, currentDelay);
    } else {
      if (callback) callback();
    }
  }
  type();
}

function parseActionText(bubble) {
  // Parse text in parentheses/brackets as action text
  const rawText = bubble.textContent;
  bubble.textContent = '';

  // Match Chinese parentheses （）and English ()
  const parts = rawText.split(/([（(][^）)]*[）)])/g);

  parts.forEach(part => {
    if (/^[（(].*[）)]$/.test(part)) {
      const span = document.createElement('span');
      span.className = 'action-text';
      span.textContent = part;
      bubble.appendChild(span);
    } else if (part) {
      const span = document.createElement('span');
      span.className = 'dialogue-text';
      span.textContent = part;
      bubble.appendChild(span);
    }
  });
}

// ── UI Helpers ──
function formatTime(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

function getSenderName(role) {
  if (role === 'user') {
    return currentConfig.user_name || '你';
  }
  // AI name from config or persona
  return currentConfig.persona || 'AI';
}

function addMessage(text, role) {
  messageCount++;
  hideWelcome();

  const isGrouped = (role === lastSenderRole) &&
    lastMessageTime && (Date.now() - lastMessageTime) < GROUP_GAP_MS;

  const div = document.createElement('div');
  div.className = `message ${role}` + (isGrouped ? ' grouped' : '');

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';

  const hasAvatar = currentConfig[`has_avatar_${role}`];
  if (hasAvatar) {
    avatar.innerHTML = `<img src="/api/avatar/${role}?t=${Date.now()}" class="avatar-img">`;
  } else {
    avatar.textContent = role === 'ai' ? '✨' : '👤';
  }

  const content = document.createElement('div');
  content.className = 'message-content';

  if (!isGrouped) {
    const sender = document.createElement('div');
    sender.className = 'message-sender';
    sender.textContent = getSenderName(role);
    content.appendChild(sender);
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;
  parseActionText(bubble);
  content.appendChild(bubble);

  const time = document.createElement('div');
  time.className = 'message-time';
  time.textContent = formatTime(new Date());
  content.appendChild(time);

  div.appendChild(avatar);
  div.appendChild(content);
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;

  lastSenderRole = role;
  lastMessageTime = Date.now();
}

function updateStatusDisplay() {
  const mbti = currentConfig.mbti || 'ENFP';
  if (currentEmotion) {
    statusText.textContent = `在线 · ${mbti} · ${currentEmotion}`;
  } else {
    statusText.textContent = `在线 · ${mbti}`;
  }
}

function addSystemMessage(text) {
  addMessage(text, 'ai');
}

function showTyping() {
  setOnline(false);
  hideWelcome();
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
    avatar.textContent = '🌙';
  }

  const content = document.createElement('div');
  content.className = 'message-content';

  const sender = document.createElement('div');
  sender.className = 'message-sender';
  sender.textContent = getSenderName('ai');

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  content.appendChild(sender);
  content.appendChild(bubble);

  div.appendChild(avatar);
  div.appendChild(content);
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
  sendBtn.disabled = false;
  sendBtn.classList.remove('loading');
}

function setOnline(online) {
  statusDot.style.background = online ? '#22c55e' : '#ef4444';
  statusDot.style.boxShadow = online ? '0 0 6px rgba(34, 197, 94, 0.4)' : 'none';
  if (online) {
    updateStatusDisplay();
  } else {
    statusText.textContent = '思考中…';
  }
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Persona Generation ──
let pendingPersona = null;

async function generatePersona() {
  const desc = document.getElementById('inputPersonaDesc').value.trim();
  if (!desc) {
    showToast('请先描述你想要的角色');
    return;
  }

  const btn = document.getElementById('generatePersonaBtn');
  btn.textContent = '生成中…';
  btn.disabled = true;

  try {
    const res = await fetch('/api/generate-persona', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '生成失败');
    }

    const data = await res.json();
    if (data.status === 'ok') {
      pendingPersona = data.persona;
      showPersonaPreview(data.persona);
    }
  } catch (e) {
    showToast('❌ ' + e.message);
  } finally {
    btn.textContent = '✨ 智能生成';
    btn.disabled = false;
  }
}

function showPersonaPreview(persona) {
  const p = persona.personality || {};
  const style = persona.speaking_style || {};
  const bg = persona.background || {};

  const html = `
    <div class="persona-preview-section">
      <div class="label">名称</div>
      <div class="value">${escHtml(persona.name || '未命名')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">描述</div>
      <div class="value">${escHtml(persona.description || '')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">核心特质</div>
      <div class="value">${(p.core_traits || []).map(t => `<span class="trait-tag">${escHtml(t)}</span>`).join('')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">打招呼</div>
      <div class="value">${escHtml(persona.greeting || '')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">语气词</div>
      <div class="value">${(style.particles || []).map(t => `<span class="trait-tag">${escHtml(t)}</span>`).join('')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">肢体动作</div>
      <div class="value">${(style.actions || []).map(t => `<span class="trait-tag">${escHtml(t)}</span>`).join('')}</div>
    </div>
    <div class="persona-preview-section">
      <div class="label">关系</div>
      <div class="value">${escHtml(bg.relationship || '')}</div>
    </div>
  `;

  document.getElementById('personaPreview').innerHTML = html;
  document.getElementById('personaModal').classList.add('show');
}

function closePersonaModal() {
  document.getElementById('personaModal').classList.remove('show');
  pendingPersona = null;
}

async function confirmPersona() {
  if (!pendingPersona) return;

  const safeName = (pendingPersona.name || 'generated_character').replace(/[^a-zA-Z0-9\u4e00-\u9fff _-]/g, '').trim();
  const filename = safeName || 'generated_character';

  try {
    const res = await fetch('/api/save-persona', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: filename, persona: pendingPersona }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '保存失败');
    }

    const data = await res.json();
    closePersonaModal();
    document.getElementById('inputPersonaDesc').value = '';

    await loadPersonas();
    document.getElementById('selPersona').value = data.persona.name;

    showToast(`角色 "${data.persona.label}" 已创建`);
    switchView('chat');
  } catch (e) {
    showToast('❌ ' + e.message);
  }
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Persona Delete ──
async function deletePersona() {
  const sel = document.getElementById('selPersona');
  const name = sel.value;
  if (!name) {
    showToast('请先选择要删除的角色');
    return;
  }
  if (!confirm(`确定删除角色 "${name}" 吗？此操作不可恢复。`)) {
    return;
  }
  try {
    const res = await fetch('/api/delete-persona', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '删除失败');
    showToast(`角色 "${name}" 已删除`);
    await loadPersonas();
    // 保存配置时刷新当前选中
    const config = await fetch('/api/config').then(r => r.json());
    if (config.persona && document.getElementById('selPersona').options.length) {
      document.getElementById('selPersona').value = config.persona;
    }
  } catch (e) {
    showToast('❌ ' + e.message);
  }
}

// ── Diary ──

async function loadDiary() {
  const list = document.getElementById('diaryList');
  const detailPanel = document.getElementById('diaryDetailPanel');
  detailPanel.innerHTML = '<div class="diary-detail-empty"><p>← 选择一篇日记查看</p></div>';
  list.innerHTML = '<div class="diary-loading">加载中…</div>';

  try {
    const res = await fetch('/api/diary?limit=50');
    const data = await res.json();

    if (!data.entries || data.entries.length === 0) {
      list.innerHTML = `
        <div class="diary-empty">
          <div class="diary-empty-icon">✨</div>
          <p>还没有日记记录</p>
          <p style="font-size:13px;margin-top:8px">AI 会在日常互动中写下感受</p>
        </div>`;
      document.getElementById('diaryCount').textContent = '';
      return;
    }

    document.getElementById('diaryCount').textContent = `${data.total} 篇`;
    list.innerHTML = data.entries.map(entry => `
      <div class="diary-entry" data-date="${entry.date}" onclick="openDiaryDetail('${entry.date}', this)">
        <div>
          <span class="diary-entry-date">${formatDiaryDate(entry.date)}</span>
          ${entry.mood ? `<span class="diary-entry-mood">${entry.mood}</span>` : ''}
        </div>
        <div class="diary-entry-preview">${escapeHtml(entry.content)}</div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = `<div class="diary-empty"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
  }
}

function formatDiaryDate(dateStr) {
  try {
    const d = new Date(dateStr);
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`;
  } catch {
    return dateStr;
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function openDiaryDetail(date, el) {
  // Highlight selected entry
  document.querySelectorAll('.diary-entry').forEach(e => e.classList.remove('selected'));
  if (el) el.classList.add('selected');

  const detailPanel = document.getElementById('diaryDetailPanel');
  detailPanel.innerHTML = '<div class="diary-loading" style="padding:40px 0;text-align:center;color:var(--text-muted)">加载中…</div>';

  try {
    const res = await fetch(`/api/diary?date=${encodeURIComponent(date)}`);
    if (!res.ok) {
      detailPanel.innerHTML = '<div class="diary-detail-empty"><p>未找到该日期的日记</p></div>';
      return;
    }
    const data = await res.json();
    const entry = data.entry;
    detailPanel.innerHTML = `
      <div class="diary-detail-card">
        <div class="diary-detail-date">${formatDiaryDate(entry.date)}</div>
        ${entry.mood ? `<div class="diary-detail-mood">心情：${escapeHtml(entry.mood)}</div>` : ''}
        <div class="diary-detail-text">${escapeHtml(entry.content)}</div>
      </div>
    `;
  } catch (e) {
    detailPanel.innerHTML = `<div class="diary-detail-empty"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
  }
}

// ── Start ──
init();
