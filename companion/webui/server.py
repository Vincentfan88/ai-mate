"""AI 伙伴 WebUI 服务器 — FastAPI + WebSocket。"""

import asyncio
import contextlib
import io
import json
import logging
import os
import shutil
import struct
import tempfile
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from companion.cli import build_companion_agent
from companion.webui.agent_wrapper import SilentAgentWrapper
from companion.modules.feishu.bot import FeishuBot
from mini_agent.schema.schema import Message

logger = logging.getLogger("companion")

# ── 全局状态 ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# ── 从环境变量加载系统参数（支持 .env 文件） ──
load_dotenv()

# 当前配置 — 系统参数从环境变量读取，用户参数从磁盘 config.json 读取
_config = {
    # 用户设定（可修改，持久化到 config.json）
    "mbti": "ENFP",
    "persona": "default",
    "user_name": "",
    "budget": 0,
    "quiet_hours_blocks": [[0, 6]],
    "quiet_hours_start": 0,
    "quiet_hours_end": 6,
    # 系统参数（来自环境变量，运行时可改但不持久化）
    "model": os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
    "api_base": os.environ.get("LLM_API_BASE", "https://api.deepseek.com/v1"),
    "api_key": os.environ.get("LLM_API_KEY", ""),
    "max_steps": 5,
    "workspace": "workspace/companion",
    "cloud_price_in": float(os.environ.get("CLOUD_PRICE_IN", "1.0")),
    "cloud_price_out": float(os.environ.get("CLOUD_PRICE_OUT", "4.0")),
    "price_cache_in": float(os.environ.get("PRICE_CACHE_IN", "0.1")),
    "local_model_enabled": os.environ.get("LOCAL_MODEL_ENABLED", "false").lower() == "true",
    "local_model": os.environ.get("LOCAL_MODEL", "qwen3-4b"),
    "local_api_base": os.environ.get("LOCAL_API_BASE", "http://127.0.0.1:1234/v1"),
    "feishu_app_id": os.environ.get("FEISHU_APP_ID", ""),
    "feishu_app_secret": os.environ.get("FEISHU_APP_SECRET", ""),
    "feishu_chat_id": os.environ.get("FEISHU_CHAT_ID", ""),
    "feishu_enabled": os.environ.get("FEISHU_ENABLED", "false").lower() == "true",
    # 后台循环总开关
    "proactive_enabled": True,
}

# 缓存 agent 实例
_agent_ref = None  # (config_hash, SilentAgentWrapper)

# 飞书 Bot 实例
_feishu_bot = None

# 主动触发循环
_proactive_loop = None
_trending_fetcher = None

# 无痕模式沙盒 agent — 与主 agent 完全独立
_sandbox_agent = None          # (tempdir, SilentAgentWrapper, persona_dict) 或 None
_sandbox_enabled = False       # 当前是否处于无痕模式
_sandbox_persona_name = None   # 私密角色名称

# 配置持久化文件路径 — 保存用户设定
CONFIG_FILE = Path("workspace/companion/config.json")

# 可持久化的配置字段（前端"保存"时写入 config.json）
# 注意：这些字段也会从 .env 环境变量加载，config.json 中的值会覆盖 .env 的默认值
# 敏感密钥（feishu_app_secret）只从 .env 读取，不写入磁盘；api_key 例外，可保存到 config.json
_USER_KEYS = {
    # 用户行为设定
    "mbti", "persona", "user_name", "budget",
    "quiet_hours_blocks", "quiet_hours_start", "quiet_hours_end",
    # 飞书 Bot（非敏感配置）
    "feishu_app_id", "feishu_chat_id", "feishu_enabled",
    # 本地模型（系统参数但需前端可配）
    "local_model_enabled", "local_model", "local_api_base",
    # 模型配置
    "model", "api_base", "api_key",
    "cloud_price_in", "cloud_price_out", "price_cache_in",
    # 后台循环开关
    "proactive_enabled",
}


def _load_config() -> None:
    """从磁盘加载用户设定（覆盖默认值）"""
    global _config
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in saved.items():
                if k in _USER_KEYS and k in _config:
                    _config[k] = v
            logger.info(f"用户配置已从磁盘加载: {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"用户配置加载失败，使用默认值: {e}")


def _save_config() -> None:
    """仅保存用户设定到磁盘，不保存系统参数"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        user_config = {k: _config[k] for k in _USER_KEYS if k in _config}
        CONFIG_FILE.write_text(
            json.dumps(user_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"用户配置保存失败: {e}")

def _inject_conversation_history(agent, registry) -> None:
    """把最近对话历史加载到 Agent 的 messages 列表中（紧跟系统提示词之后）。

    这样 LLM 每次启动都能知道最近的上下文，不用依赖手动调用记忆工具。
    """
    try:
        recent = registry.memory.get_recent_conversations(limit=20)
        if not recent:
            return

        try:
            ai_name = registry.memory.persona.get("name", "小美")
        except (AttributeError, KeyError):
            ai_name = "小美"

        # 插入到系统消息之后（messages[0] 是系统提示词）
        # 用 system 角色注入，避免被当成对话历史
        history_lines = ["（以下是你们最近的对话记录，供你参考回忆）"]
        for entry in recent:
            if entry["role"] == "assistant":
                history_lines.append(f"{ai_name}: {entry['content']}")
            else:
                history_lines.append(f"对方: {entry['content']}")
        history_text = "\n".join(history_lines)
        agent.messages.append(Message(role="system", content=history_text))
        logger.info(f"已加载 {len(recent)} 条最近对话到 Agent 上下文")
    except Exception as e:
        logger.warning(f"加载对话历史失败: {e}")

# WebSocket 连接的客户端集合
_ws_clients: list = []
_ws_lock: asyncio.Lock | None = None  # 延迟初始化

def _get_ws_lock() -> asyncio.Lock:
    global _ws_lock
    if _ws_lock is None:
        _ws_lock = asyncio.Lock()
    return _ws_lock


def _config_hash() -> str:
    return json.dumps(_config, sort_keys=True)


def _get_or_create_agent():
    """获取或重建 agent（配置变化时自动重建）。"""
    global _agent_ref
    h = _config_hash()
    if _agent_ref is not None and _agent_ref[0] == h:
        return _agent_ref[1]

    persona_file = f"{BASE_DIR.parent / 'skills' / 'companion' / _config['persona']}.json"
    agent, registry, persona = build_companion_agent(
        mbti_type=_config["mbti"],
        persona_name=_config["persona"],
        model=_config["model"],
        api_base=_config["api_base"],
        api_key=_config["api_key"],
        max_steps=_config["max_steps"],
        workspace=_config["workspace"],
        persona_path=str(persona_file),
        local_model_enabled=_config.get("local_model_enabled", False),
        local_model=_config.get("local_model", ""),
        local_api_base=_config.get("local_api_base", ""),
        user_name=_config.get("user_name", ""),
        trigger_quiet_hours=_config.get("quiet_hours_blocks", [[0, 6]]),
    )
    wrapper = SilentAgentWrapper(agent, registry)

    # Agent 启动时加载最近对话历史到 messages（让 LLM 知道上下文）
    _inject_conversation_history(agent, registry)

    _agent_ref = (h, wrapper, persona)

    # 注入价格配置到 token_tracker
    from companion.token_tracker import token_tracker
    token_tracker.set_price(
        model=_config["model"],
        price_in=_config.get("cloud_price_in", 1.0),
        price_out=_config.get("cloud_price_out", 4.0),
        price_cache_in=_config.get("price_cache_in", 0.1),
    )
    # 本地模型免费
    if _config.get("local_model_enabled"):
        local_model_name = _config.get("local_model", "")
        if local_model_name:
            token_tracker.set_price(
                model=local_model_name,
                price_in=0.0,
                price_out=0.0,
                price_cache_in=0.0,
            )

    return wrapper


def _get_persona_info() -> dict:
    """获取当前人格信息。"""
    if _agent_ref is not None:
        return {"name": _agent_ref[2].get("name", ""), "greeting": _agent_ref[2].get("greeting", "")}
    return {"name": "", "greeting": ""}


def _get_available_personas() -> list:
    """列出可用人格配置。"""
    skills_dir = BASE_DIR.parent / "skills" / "companion"
    personas = []
    if skills_dir.exists():
        for f in sorted(skills_dir.glob("*.json")):
            name = f.stem
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                label = data.get("name") or data.get("char_name", name)
            except Exception:
                label = name
            personas.append({"name": name, "label": label})
    return personas


# ── 飞书 Bot 生命周期 ────────────────────────────────────────


def _start_feishu_bot() -> None:
    """根据当前配置启动飞书 Bot。"""
    global _feishu_bot
    if not _config.get("feishu_enabled") or not _config.get("feishu_app_id"):
        return
    loop = asyncio.get_event_loop()
    _feishu_bot = FeishuBot(
        app_id=_config["feishu_app_id"],
        app_secret=_config["feishu_app_secret"],
        loop=loop,
    )
    _feishu_bot.set_agent_getter(_get_or_create_agent_wrapper)
    _feishu_bot.start()


def _stop_feishu_bot() -> None:
    """停止飞书 Bot。"""
    global _feishu_bot
    if _feishu_bot:
        _feishu_bot.stop()
        _feishu_bot = None


def _get_or_create_agent_wrapper() -> SilentAgentWrapper:
    """获取或创建 agent wrapper（供飞书 Bot 共享）。"""
    return _get_or_create_agent()


# ── 沙盒（无痕模式）生命周期 ───────────────────────────────────


def _create_sandbox_agent(persona_path: str | None = None) -> tuple:
    """创建沙盒 agent — 使用临时目录作为 workspace。

    返回 (tempdir, wrapper, persona) 元组。
    """
    global _config
    tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
    sandbox_workspace = tempdir.name

    logger.info(f"[Sandbox] 创建临时 workspace: {sandbox_workspace}")

    try:
        # 使用默认 persona 路径，除非指定了私密角色卡
        if persona_path is None:
            persona_path = str(BASE_DIR.parent / "skills" / "companion" / "default.json")

        agent, registry, persona = build_companion_agent(
            mbti_type=_config.get("mbti"),
            persona_name=_config.get("persona", "sandbox"),
            model=_config.get("model"),
            api_base=_config.get("api_base"),
            api_key=_config.get("api_key"),
            workspace=sandbox_workspace,
            persona_path=persona_path,
            max_steps=_config.get("max_steps"),
        )
        if agent is None:
            raise RuntimeError("Failed to build sandbox agent")

        wrapper = SilentAgentWrapper(agent, registry)
        return (tempdir, wrapper, persona)
    except Exception:
        tempdir.cleanup()
        raise


def _destroy_sandbox() -> None:
    """销毁沙盒 agent + 清理临时目录。"""
    global _sandbox_agent, _sandbox_enabled, _sandbox_persona_name

    if _sandbox_agent:
        tempdir, wrapper, _ = _sandbox_agent
        try:
            tempdir.cleanup()
            logger.info("[Sandbox] 临时目录已销毁")
        except Exception as e:
            logger.warning(f"[Sandbox] 清理临时目录失败: {e}")
        _sandbox_agent = None

    _sandbox_enabled = False
    _sandbox_persona_name = None


# ── 主动触发 + 消息路由 ────────────────────────────────────────


async def _ws_broadcast(msg: dict) -> None:
    """向所有 WebSocket 客户端广播消息。"""
    lock = _get_ws_lock()
    async with lock:
        clients = list(_ws_clients)
    dead_clients = []
    for client in clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead_clients.append(client)
    # 清理已断开的连接
    if dead_clients:
        async with lock:
            for client in dead_clients:
                try:
                    _ws_clients.remove(client)
                except ValueError:
                    pass


async def _on_proactive_trigger(event: dict) -> None:
    """ProactiveLoop 回调 — 生成主动消息并发送。

    私密模式下跳过主动触发，避免主系统的主动性模块乱入私密对话。
    """
    global _sandbox_enabled
    if _sandbox_enabled:
        logger.debug("[Proactive] 私密模式已开启，跳过主动触发")
        return

    decision = event["decision"]
    wrapper = _get_or_create_agent()

    # 记录触发决策到日志
    logger.info(
        f"[Proactive] trigger={event.get('type', '?')} state={decision['state']} "
        f"nudge={decision['nudge']} pull={decision['pull'][:30]} "
        f"connection={decision.get('connection', '?')}"
    )

    # 构造触发上下文提示词
    prompt = (
        f"你当前的状态：{decision['state']}，冲动：{decision['nudge']}，"
        f"想联系他的理由：{decision['pull']}，忍住的理由：{decision['hold_back']}。"
        f"基于以上状态，用符合人格的方式自然地发起一段对话，可以分享一个想法或感受，"
        f"不要太长，一句话就好。不要生硬。"
    )

    try:
        response = await wrapper.run(prompt)

        # 获取情绪
        try:
            emotion_info = wrapper.registry.emotion.get_current_emotion("time_passage")
            current_emotion = emotion_info.get("emotion", "")
        except Exception:
            current_emotion = ""

        if response and not response.startswith("LLM call failed") and not response.startswith("Task couldn't be completed") and response != "(empty response)":
            # 通过飞书发送
            if _feishu_bot and _feishu_bot.is_connected:
                default_chat_id = _config.get("feishu_chat_id", "")
                if default_chat_id:
                    await _feishu_bot._send_reply(default_chat_id, response)
            # 广播到 WebUI（含情绪信息）
            await _ws_broadcast({"type": "proactive", "content": response, "emotion": current_emotion})
            # 活人感：记录主动联系
            if wrapper.registry:
                wrapper.registry.liveness.record_initiated_contact()
            logger.info(f"[Proactive] 主动发送: {response[:50]}")
        elif response:
            logger.warning(f"[Proactive] LLM 拒绝响应")
    except Exception as e:
        logger.error(f"[Proactive] 主动触发失败: {e}")


# ── FastAPI 应用 ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _proactive_loop, _trending_fetcher

    # 从磁盘加载配置
    _load_config()

    # 启动飞书 Bot
    _start_feishu_bot()

    # 启动主动触发循环 + 热搜预取（仅在开关开启时）
    from companion.scheduler import ProactiveLoop, TrendingFetcher
    wrapper = _get_or_create_agent()
    registry = wrapper.registry if wrapper else None
    if registry and _config.get("proactive_enabled", True):
        _proactive_loop = ProactiveLoop(registry, on_trigger=_on_proactive_trigger)
        asyncio.create_task(_proactive_loop.run())
        _trending_fetcher = TrendingFetcher(
            registry,
            api_key=_config.get("api_key", ""),
            api_base=_config.get("api_base", ""),
            model=_config.get("model", ""),
        )
        asyncio.create_task(_trending_fetcher.run())
        logger.info("主动触发循环已启动")
    else:
        logger.info("主动触发循环已禁用（后台模式）")

    yield

    # 清理
    _stop_feishu_bot()
    if _proactive_loop:
        _proactive_loop.stop()
        _proactive_loop = None
    if _trending_fetcher:
        _trending_fetcher.stop()
        _trending_fetcher = None
    global _agent_ref
    _agent_ref = None


app = FastAPI(lifespan=lifespan)


# ── 角色卡导入 ──────────────────────────────────────────────


SKILLS_DIR = BASE_DIR.parent / "skills" / "companion"


def _parse_png_chara(data: bytes) -> dict:
    """从 PNG 的 tEXt chunk 中提取 chara 角色卡 JSON。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是有效的 PNG 文件")
    pos = 8
    while pos + 8 < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        # 防御畸形 chunk：长度超出数据范围
        if pos + 8 + length > len(data):
            break
        chunk_type = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + length]
        if chunk_type == b"tEXt":
            null_pos = chunk_data.find(b"\x00")
            if null_pos >= 0:
                keyword = chunk_data[:null_pos].decode("latin-1")
                text = chunk_data[null_pos + 1:].decode("utf-8", errors="replace")
                if keyword == "chara":
                    return json.loads(text)
        pos += 12 + length
    raise ValueError("PNG 中未找到角色数据 (chara chunk)")


def _parse_character_card(content: bytes, filename: str) -> dict:
    """解析 PNG 或 JSON 角色卡，返回规范化角色数据。"""
    if filename.lower().endswith(".png"):
        card = _parse_png_chara(content)
    else:
        card = json.loads(content.decode("utf-8"))

    # V2 spec: data 在 card["data"] 中
    if isinstance(card, dict) and card.get("spec") == "chara_card_v2":
        data = card.get("data", card)
    else:
        data = card

    return data


def _card_to_persona(data: dict) -> dict:
    """将 SillyTavern 角色卡转换为 companion ng 人格格式。"""
    name = data.get("name", "Imported")
    description = data.get("description", f"来自角色卡导入的 {name}")
    personality_text = data.get("personality", "")
    scenario = data.get("scenario", "")
    first_mes = data.get("first_mes", "")
    system_prompt = data.get("system_prompt", "")
    post_history = data.get("post_history_instructions", "")

    # 解析 personality 文本为核心特质（限制 10 行，防止 prompt 膨胀）
    traits = []
    if personality_text:
        for line in personality_text.strip().split("\n")[:10]:
            line = line.strip()
            if line:
                traits.append(line)

    if not traits:
        traits = [f"你是{name}，{description}"]
    if scenario:
        traits.append(f"场景设定：{scenario}")

    persona = {
        "name": name,
        "description": description,
        "version": "2.0",
        "personality": {
            "core_traits": traits,
            "moods": {
                "happy": "语气轻快",
                "worried": "温柔担心",
                "missing": "表达思念",
                "shy": "害羞",
                "jealous": "小醋意",
                "sleepy": "困困的",
            },
            "forbidden": [
                "不要说'作为AI'或'我只是一个程序'",
                "不要一次说太多话",
                "不要过于完美",
            ],
        },
        "speaking_style": {
            "actions": ["自然地表达"],
            "particles": [],
            "emojis": [],
            "max_length": 120,
        },
        "greeting": first_mes or f"你好呀，我是{name}~",
    }

    # 保留角色卡自带的 system_prompt，供 build_system_prompt 直接使用
    if system_prompt:
        persona["system_prompt"] = system_prompt

    # 附加 post_history / scenario 作为额外指令
    extra_parts = []
    if post_history:
        extra_parts.append(post_history)
    if extra_parts:
        persona["extra_instructions"] = "\n".join(extra_parts)

    return persona


@app.post("/api/import-character")
async def import_character(file: UploadFile = File(...)):
    """导入酒馆角色卡（PNG 或 JSON），保存为人格配置。"""
    try:
        content = await file.read()
        data = _parse_character_card(content, file.filename or "card.json")
        persona = _card_to_persona(data)

        safe_name = "".join(c for c in persona["name"] if c.isalnum() or c in " _-").strip()
        safe_name = re.sub(r'[\s_-]+', '-', safe_name)  # 合并连续空格/下划线/短横线
        if not safe_name:
            safe_name = "imported_character"
        filename = f"{safe_name}.json"

        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = SKILLS_DIR / filename

        # 验证解析后的路径仍在 SKILLS_DIR 内
        resolved = out_path.resolve()
        if not str(resolved).startswith(str(SKILLS_DIR.resolve())):
            raise ValueError("非法的文件路径")

        out_path.write_text(
            json.dumps(persona, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return JSONResponse({
            "status": "ok",
            "persona": {"name": filename.replace(".json", ""), "label": persona["name"]},
            "greeting": persona["greeting"],
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无法解析角色卡 JSON 数据")
    except Exception as e:
        logger.error(f"[ImportCharacter] 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="导入失败，请检查文件格式")


@app.post("/api/generate-persona")
async def generate_persona(body: dict):
    """根据用户自然语言描述智能生成角色卡。"""
    description = (body.get("description", "") or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="请提供角色描述")

    system_prompt = (
        "你是一个角色卡生成助手。根据用户的自然语言描述，生成符合规范的 AI 伴侣角色配置 JSON。\n"
        "用户会输入一段关于角色的描述，你需要从中提取/推断出以下字段：\n"
        "- name: 角色名称\n"
        "- description: 简短描述\n"
        "- version: '2.0'\n"
        "- personality.core_traits: 核心特质列表（从描述中提取，3-7 条）\n"
        "- personality.moods: 情绪表达（happy/worried/missing/shy/jealous/sleepy 各一句）\n"
        "- personality.forbidden: 行为禁忌列表（2-4 条，如不要说自己是 AI、不要一次说太多等）\n"
        "- speaking_style.actions: 动作列表（5-10 条，符合角色性格的肢体互动）\n"
        "- speaking_style.particles: 语气词列表（3-6 个）\n"
        "- speaking_style.emojis: 常用 emoji（5-10 个）\n"
        "- speaking_style.max_length: 数字（80-150）\n"
        "- greeting: 角色打招呼的第一句话\n"
        "- background.relationship: 关系描述\n"
        "- system_prompt_template: 系统提示模板\n"
        "只返回合法的 JSON，不要有其他文字。"
    )

    # 尝试用云端模型生成；失败则用 fallback 模板
    try:
        api_base = _config.get("api_base", "https://api.deepseek.com/v1")
        api_key = _config.get("api_key", "")
        model = _config.get("model", "deepseek-v4-flash")

        api_lower = api_base.lower()
        if "anthropic" in api_lower:
            provider = "anthropic"
        else:
            provider = "openai"

        from mini_agent import LLMClient
        from mini_agent.retry import RetryConfig

        llm = LLMClient(
            api_key=api_key,
            provider=provider,
            api_base=api_base,
            model=model,
            retry_config=RetryConfig(enabled=True, max_retries=1),
        )

        from mini_agent.agent import Agent
        agent = Agent(
            llm_client=llm,
            system_prompt=system_prompt,
            tools={},
            max_steps=5,
        )
        agent.add_user_message(f"请根据以下描述生成角色卡：{description}")
        result = await agent.run()

        if result and not result.startswith("LLM call failed"):
            # 尝试从返回中提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                persona_data = json.loads(json_match.group())
                persona_data["version"] = "2.0"
                return JSONResponse({"status": "ok", "persona": persona_data})
    except Exception as e:
        logging.getLogger("companion").warning(f"LLM 生成角色失败: {e}")

    # Fallback: 基于关键词的简单模板
    persona_data = _generate_persona_fallback(description)
    return JSONResponse({"status": "ok", "persona": persona_data})


def _generate_persona_fallback(description: str) -> dict:
    """基于关键词的简单角色生成（LLM 不可用时的兜底）。"""
    # 简单提取名称
    name = description[:10].strip()
    if not name:
        name = "AI 角色"

    return {
        "name": name,
        "description": description,
        "version": "2.0",
        "personality": {
            "core_traits": [description, "有自己的想法和情绪"],
            "moods": {
                "happy": "语气轻快",
                "worried": "温柔关心",
                "missing": "表达思念",
                "shy": "害羞腼腆",
                "jealous": "小醋意",
                "sleepy": "困倦慵懒",
            },
            "forbidden": [
                "不要说'作为AI'或'我只是一个程序'",
                "不要一次说太多话",
            ],
        },
        "speaking_style": {
            "actions": ["自然地表达"],
            "particles": ["呀", "呢", "啦"],
            "emojis": ["😊", "✨", "💕"],
            "max_length": 100,
        },
        "greeting": f"嗨，我是{name}~",
        "background": {
            "relationship": "亲密关系",
        },
        "system_prompt_template": f"你是{name}，{description}。",
    }


# ── 头像 ──────────────────────────────────────────────────
# 头像存放在共享目录（所有角色共用），不随 persona 隔离


def _avatar_dir() -> Path:
    base = _config.get("workspace", "workspace/companion")
    return Path(f"{base}/avatars")


def _avatar_path(role: str) -> Path:
    return _avatar_dir() / f"{role}.png"


def _has_avatar(role: str) -> bool:
    return _avatar_path(role).exists()


@app.post("/api/upload-avatar/{role}")
async def upload_avatar(role: str, file: UploadFile = File(...)):
    """上传头像（ai 或 user）。"""
    if role not in ("ai", "user"):
        raise HTTPException(status_code=400, detail="角色必须是 ai 或 user")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只接受图片文件")

    try:
        _avatar_dir().mkdir(parents=True, exist_ok=True)
        content = await file.read()
        _avatar_path(role).write_bytes(content)
        return {"status": "ok", "role": role, "has_avatar": True}
    except Exception as e:
        logger.error(f"[Avatar] 上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="上传失败，请稍后重试")


@app.post("/api/save-persona")
async def save_persona(body: dict):
    """保存生成的角色卡为 persona 配置文件。"""
    name = (body.get("name", "generated") or "").strip()
    persona = body.get("persona")
    if not persona:
        raise HTTPException(status_code=400, detail="角色数据为空")

    if not name:
        name = "generated_character"

    # 确保路径安全
    filename = "".join(c for c in name if c.isalnum() or c in " _-").strip() + ".json"
    if not filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法的文件名")

    out_path = SKILLS_DIR / filename
    resolved = out_path.resolve()
    if not str(resolved).startswith(str(SKILLS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法的文件路径")

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(persona, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return JSONResponse({
        "status": "ok",
        "persona": {"name": filename.replace(".json", ""), "label": persona.get("name", name)},
    })


@app.get("/api/avatar/{role}")
async def get_avatar(role: str):
    """获取头像图片。"""
    if role not in ("ai", "user"):
        raise HTTPException(status_code=400, detail="角色必须是 ai 或 user")
    path = _avatar_path(role)
    if not path.exists():
        raise HTTPException(status_code=404, detail="未设置头像")
    from fastapi.responses import FileResponse
    return FileResponse(str(path), media_type="image/png")


@app.post("/api/delete-avatar/{role}")
async def delete_avatar(role: str):
    """删除头像。"""
    if role not in ("ai", "user"):
        raise HTTPException(status_code=400, detail="角色必须是 ai 或 user")
    path = _avatar_path(role)
    if path.exists():
        path.unlink()
    return {"status": "ok", "role": role, "has_avatar": False}


@app.post("/api/delete-persona")
async def delete_persona(body: dict):
    """删除角色卡文件及其专属工作区数据。"""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名不能为空")

    # 统一使用 sanitized 名称
    safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="非法的角色名")

    filename = f"{safe_name}.json"

    # 1. 删除 persona JSON 文件
    out_path = SKILLS_DIR / filename
    resolved = out_path.resolve()
    if not str(resolved).startswith(str(SKILLS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法的文件路径")
    if not out_path.exists():
        raise HTTPException(status_code=404, detail=f"角色文件不存在: {safe_name}")
    out_path.unlink()
    logger.info(f"[DeletePersona] 已删除角色文件: {filename}")

    # 2. 删除角色专属工作区目录（严格校验：必须是 base 的直接子目录）
    base_workspace = _config.get("workspace", "workspace/companion")
    persona_workspace = Path(f"{base_workspace}/{safe_name}")
    resolved_ws = persona_workspace.resolve()
    resolved_base = Path(base_workspace).resolve()
    expected_ws = (resolved_base / safe_name).resolve()
    if resolved_ws == expected_ws and persona_workspace.exists():
        shutil.rmtree(persona_workspace)
        logger.info(f"[DeletePersona] 已删除工作区: {persona_workspace}")

    # 3. 如果是当前激活角色，重置 agent 并选择可用角色
    global _agent_ref
    if _config.get("persona") == safe_name:
        _agent_ref = None
        # 选择第一个可用角色，避免回退到不存在的 default
        available = _get_available_personas()
        _config["persona"] = available[0]["name"] if available else "default"

    return {"status": "ok", "name": safe_name}


# API 端点
@app.get("/api/personas")
async def list_personas():
    return {"personas": _get_available_personas()}


@app.get("/api/config")
async def get_config():
    info = _get_persona_info()
    # 过滤飞书密钥，返回 api_key（本地单用户应用）
    safe_config = {k: v for k, v in _config.items() if k not in ("feishu_app_secret",)}
    return {
        **safe_config,
        **info,
        "has_avatar_ai": _has_avatar("ai"),
        "has_avatar_user": _has_avatar("user"),
        "feishu_connected": _feishu_bot.is_connected if _feishu_bot else False,
        "sandbox_enabled": _sandbox_enabled,
        "sandbox_persona": _sandbox_persona_name,
    }


@app.post("/api/config")
async def update_config(body: dict):
    global _config
    for k in ("mbti", "persona", "model", "api_base", "api_key", "workspace"):
        if k in body:
            _config[k] = body[k]
    # max_steps 必须是正整数
    if "max_steps" in body:
        try:
            _config["max_steps"] = max(1, int(body["max_steps"]))
        except (TypeError, ValueError):
            logger.warning(f"Invalid max_steps value: {body.get('max_steps')}")
    for k in ("cloud_price_in", "cloud_price_out", "price_cache_in"):
        if k in body:
            try:
                _config[k] = float(body[k])
            except (TypeError, ValueError):
                logger.warning(f"Invalid {k} value: {body.get(k)}")
    if "user_name" in body:
        _config["user_name"] = body["user_name"]
    for k in ("local_model_enabled", "local_model", "local_api_base"):
        if k in body:
            _config[k] = body[k]
    for k in ("budget",):
        if k in body:
            try:
                _config[k] = float(body[k])
            except (TypeError, ValueError):
                logger.warning(f"Invalid budget value: {body.get('budget')}")
    # 免打扰时段：前端发送 quiet_hours_blocks = [[start, end], ...]
    if "quiet_hours_blocks" in body:
        blocks = body["quiet_hours_blocks"]
        if isinstance(blocks, list) and len(blocks) > 0:
            _config["quiet_hours_blocks"] = [
                [int(b["start"]), int(b["end"])] for b in blocks
                if isinstance(b, dict) and "start" in b and "end" in b
            ]
        else:
            _config["quiet_hours_blocks"] = [[0, 6]]
    # 兼容旧版单段字段（也保留更新）
    for k in ("quiet_hours_start", "quiet_hours_end"):
        if k in body:
            _config[k] = int(body[k])

    # 下次请求时自动重建 agent
    global _agent_ref
    _agent_ref = None

    # 处理飞书配置变更
    feishu_changed = False
    for k in ("feishu_app_id", "feishu_app_secret", "feishu_chat_id", "feishu_enabled"):
        if k in body:
            _config[k] = body[k]
            feishu_changed = True

    if feishu_changed:
        _stop_feishu_bot()
        _start_feishu_bot()

    # 处理后台循环开关（saveAllSettings 也会发送此字段）
    if "proactive_enabled" in body:
        _config["proactive_enabled"] = bool(body["proactive_enabled"])

    # 持久化到磁盘
    _save_config()

    return {"status": "ok", "config": _config}


@app.post("/api/mbti")
async def update_mbti(body: dict):
    """热切换 MBTI 类型，无需重建 agent，下次消息生效。"""
    mbti = body.get("mbti", "ENFP")
    valid_mbti = [
        "ENFP", "INFP", "ENTP", "INTP", "ENFJ", "INFJ", "ENTJ", "INTJ",
        "ESFP", "ISFP", "ESTP", "ISTP", "ESFJ", "ISFJ", "ESTJ", "ISTJ",
    ]
    if mbti not in valid_mbti:
        return {"status": "error", "error": f"无效的 MBTI 类型: {mbti}"}
    _config["mbti"] = mbti
    # 失效 agent 引用，下次消息自动重建
    global _agent_ref
    _agent_ref = None
    _save_config()
    return {"status": "ok", "mbti": mbti}


@app.post("/api/reload")
async def reload_agent():
    """强制重建 agent。"""
    global _agent_ref
    _agent_ref = None
    _get_or_create_agent()
    return {"status": "ok"}


@app.get("/api/feishu/status")
async def feishu_status():
    """获取飞书 Bot 连接状态。"""
    global _feishu_bot
    if not _config.get("feishu_enabled") or not _config.get("feishu_app_id"):
        return {"status": "disabled", "connected": False}
    connected = _feishu_bot.is_connected if _feishu_bot else False
    return {"status": "connected" if connected else "disconnected", "connected": connected}


@app.get("/api/token-stats")
async def token_stats():
    """获取本月 Token 消耗统计。"""
    from companion.token_tracker import token_tracker
    import calendar
    now = datetime.now()
    # 当月第一天 00:00:00 (北京时间 UTC+8)
    month_start = datetime(now.year, now.month, 1).isoformat()
    stats = token_tracker.get_stats(since=month_start)
    # 附加月份信息
    year = now.year
    month = now.month
    _, days_in_month = calendar.monthrange(year, month)
    stats["current_month"] = f"{year}-{month:02d}"
    stats["days_elapsed"] = now.day
    stats["days_total"] = days_in_month
    # 将 model_breakdown 中的价格对象简化，避免序列化问题
    for m, mb in stats.get("model_breakdown", {}).items():
        if "price" in mb:
            del mb["price"]
    return stats


@app.post("/api/token-reset")
async def token_reset():
    """清空 Token 统计。"""
    from companion.token_tracker import token_tracker
    token_tracker.reset()
    return {"status": "ok"}


# ── 后台循环开关 API ──────────────────────────────────────


@app.post("/api/proactive/toggle")
async def toggle_proactive(body: dict):
    """开启/关闭主动触发和热搜预取后台循环。"""
    global _proactive_loop, _trending_fetcher

    enabled = body.get("enabled", True)

    if enabled:
        # 已开启则不重复创建
        if _proactive_loop:
            return {"status": "ok", "enabled": True, "message": "后台循环已开启"}

        try:
            from companion.scheduler import ProactiveLoop, TrendingFetcher
            wrapper = _get_or_create_agent()
            registry = wrapper.registry if wrapper else None
            if not registry:
                raise RuntimeError("Agent registry not available")
            _proactive_loop = ProactiveLoop(registry, on_trigger=_on_proactive_trigger)
            asyncio.create_task(_proactive_loop.run())
            _trending_fetcher = TrendingFetcher(
                registry,
                api_key=_config.get("api_key", ""),
                api_base=_config.get("api_base", ""),
                model=_config.get("model", ""),
            )
            asyncio.create_task(_trending_fetcher.run())
        except Exception as e:
            # 启动失败：回滚配置，不写入磁盘
            _proactive_loop = None
            _trending_fetcher = None
            _config["proactive_enabled"] = False
            logger.error(f"[Proactive] 启动失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="启动失败，请稍后重试")

        _config["proactive_enabled"] = True
        _save_config()
        logger.info("[Proactive] 后台循环已启动")
        return {"status": "ok", "enabled": True, "message": "后台循环已启动"}
    else:
        # 停止现有循环
        if _proactive_loop:
            _proactive_loop.stop()
            _proactive_loop = None
        if _trending_fetcher:
            _trending_fetcher.stop()
            _trending_fetcher = None
        _config["proactive_enabled"] = False
        _save_config()
        logger.info("[Proactive] 后台循环已停止")
        return {"status": "ok", "enabled": False, "message": "后台循环已停止，进入纯后台模式"}


# ── 无痕模式（沙盒）API ─────────────────────────────────────


@app.post("/api/sandbox/toggle")
async def toggle_sandbox(body: dict):
    """开启/关闭私密模式。

    开启: 创建沙盒 agent，workspace 指向 tempdir
    关闭: 销毁沙盒 agent + tempdir.cleanup()
    """
    global _sandbox_agent, _sandbox_enabled, _sandbox_persona_name

    enabled = body.get("enabled", False)

    if enabled and not _sandbox_enabled:
        try:
            _sandbox_agent = _create_sandbox_agent()
            _sandbox_enabled = True
            _sandbox_persona_name = _sandbox_agent[2].get("name", "sandbox")
            logger.info(f"[Sandbox] 私密模式已开启: {_sandbox_persona_name}")
            return {
                "status": "ok",
                "enabled": True,
                "persona": _sandbox_persona_name,
                "message": "私密模式已开启",
            }
        except Exception as e:
            logger.error(f"[Sandbox] 创建失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="创建失败，请稍后重试")

    elif not enabled and _sandbox_enabled:
        _destroy_sandbox()
        logger.info("[Sandbox] 私密模式已关闭")
        return {"status": "ok", "enabled": False, "message": "私密模式已关闭，记录已焚毁"}

    # 状态未变化
    return {"status": "ok", "enabled": _sandbox_enabled, "persona": _sandbox_persona_name}


@app.post("/api/sandbox/clear")
async def clear_sandbox():
    """关闭私密模式并销毁所有临时数据。"""
    global _sandbox_agent, _sandbox_enabled, _sandbox_persona_name

    if not _sandbox_enabled:
        return {"status": "ok", "message": "私密模式未开启"}

    _destroy_sandbox()
    return {"status": "ok", "message": "私密记录已焚毁"}


@app.post("/api/sandbox/import-persona")
async def sandbox_import_persona(file: UploadFile = File(...)):
    """私密模式下导入角色卡 — 存到 tempdir 内，关闭时一起销毁。

    仅在私密模式已开启时可调用。
    """
    global _sandbox_agent, _sandbox_enabled, _sandbox_persona_name

    if not _sandbox_enabled or not _sandbox_agent:
        raise HTTPException(status_code=400, detail="请先开启私密模式")

    # 文件大小限制（10MB）
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="角色卡文件过大（最大 10MB）")

    filename = file.filename or "sandbox_persona.json"

    try:
        # 解析角色卡
        data = _parse_character_card(content, filename)
        persona_data = _card_to_persona(data)

        safe_name = "".join(c for c in persona_data["name"] if c.isalnum() or c in " _-").strip()
        if not safe_name:
            safe_name = "sandbox_persona"
        persona_file = f"{safe_name}.json"

        # 先构建新 agent，成功后再原子性替换引用（避免竞态）
        new_tempdir = tempfile.TemporaryDirectory(prefix="ai-mate-sandbox-")
        new_workspace = new_tempdir.name
        new_persona_dir = Path(new_workspace) / "persona"
        new_persona_dir.mkdir(exist_ok=True)

        temp_persona_path = new_persona_dir / persona_file
        temp_persona_path.write_text(
            json.dumps(persona_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        try:
            new_agent, new_registry, new_persona_obj = build_companion_agent(
                mbti_type=_config.get("mbti"),
                persona_name=safe_name,
                model=_config.get("model"),
                api_base=_config.get("api_base"),
                api_key=_config.get("api_key"),
                workspace=new_workspace,
                persona_path=str(temp_persona_path),
                max_steps=_config.get("max_steps"),
            )
            if new_agent is None:
                raise RuntimeError("Failed to rebuild sandbox agent")

            new_wrapper = SilentAgentWrapper(new_agent, new_registry)
        except Exception:
            new_tempdir.cleanup()
            raise

        # 原子性替换：先建好再换引用
        old_tempdir, old_wrapper, old_persona = _sandbox_agent
        _sandbox_agent = (new_tempdir, new_wrapper, new_persona_obj)
        _sandbox_persona_name = persona_data["name"]

        # 清理旧 tempdir
        old_tempdir.cleanup()

        logger.info(f"[Sandbox] 私密角色已导入: {safe_name}")
        return {
            "status": "ok",
            "persona": persona_data["name"],
            "message": f"私密角色 \"{persona_data['name']}\" 已导入",
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="角色卡 JSON 格式无效")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SandboxImport] 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="导入失败，请检查文件格式")


# WebSocket — 对话
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    lock = _get_ws_lock()
    async with lock:
        _ws_clients.append(ws)
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
                    # AI 回复后设置 connection 冷却，防止短时间内再次主动触发
                    try:
                        wrapper.registry.trigger.connection_axis.on_contact()
                    except Exception as e:
                        logger.warning(f"Connection cooldown failed: {e}")
                    await ws.send_json({"type": "message", "content": response, "emotion": current_emotion, "sandbox": _sandbox_enabled})
                else:
                    await ws.send_json({"type": "error", "content": "抱歉，我出神了没听清… 能再说一遍吗？"})
            except Exception as e:
                logging.getLogger("companion").error(f"WebSocket 错误: {e}", exc_info=True)
                await ws.send_json({"type": "error", "content": "抱歉，我出错了… 请稍后再试。"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.getLogger("companion").error(f"WebSocket 连接异常: {e}", exc_info=True)
    finally:
        async with lock:
            try:
                _ws_clients.remove(ws)
            except ValueError:
                pass


# 静态文件
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
