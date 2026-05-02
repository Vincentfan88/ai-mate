"""AI 伴侣 WebUI 服务器 — FastAPI + WebSocket。"""

import io
import json
import struct
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from companion.cli import build_companion_agent
from companion.webui.agent_wrapper import SilentAgentWrapper
from companion.modules.feishu.bot import FeishuBot

# ── 全局状态 ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# 当前配置
_config = {
    "mbti": "ENFP",
    "persona": "default",
    "model": "deepseek-v4-flash",
    "api_base": "http://127.0.0.1:15721",
    "api_key": "cc-switch-proxy",
    "max_steps": 5,
    "workspace": "workspace/companion",
    "feishu_app_id": "",
    "feishu_app_secret": "",
    "feishu_enabled": False,
}

# 缓存 agent 实例
_agent_ref = None  # (config_hash, SilentAgentWrapper)

# 飞书 Bot 实例
_feishu_bot = None


def _config_hash() -> str:
    return json.dumps(_config, sort_keys=True)


def _get_or_create_agent():
    """获取或重建 agent（配置变化时自动重建）。"""
    global _agent_ref
    h = _config_hash()
    if _agent_ref is not None and _agent_ref[0] == h:
        return _agent_ref[1]

    agent, registry, persona = build_companion_agent(
        mbti_type=_config["mbti"],
        persona_name=_config["persona"],
        model=_config["model"],
        api_base=_config["api_base"],
        api_key=_config["api_key"],
        max_steps=_config["max_steps"],
        workspace=_config["workspace"],
    )
    wrapper = SilentAgentWrapper(agent, registry)
    _agent_ref = (h, wrapper, persona)
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


# ── FastAPI 应用 ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时预热
    _start_feishu_bot()
    yield
    # 清理
    _stop_feishu_bot()
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

    # 解析 personality 文本为核心特质
    traits = []
    if personality_text:
        for line in personality_text.strip().split("\n"):
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

    # 附加 system_prompt / post_history / scenario
    extra_parts = []
    if system_prompt:
        extra_parts.append(system_prompt)
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
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ── 头像 ──────────────────────────────────────────────────


AVATAR_DIR = Path("workspace/companion/avatars")


def _avatar_path(role: str) -> Path:
    return AVATAR_DIR / f"{role}.png"


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
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        _avatar_path(role).write_bytes(content)
        return {"status": "ok", "role": role, "has_avatar": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


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


# API 端点
@app.get("/api/personas")
async def list_personas():
    return {"personas": _get_available_personas()}


@app.get("/api/config")
async def get_config():
    info = _get_persona_info()
    return {
        **_config,
        **info,
        "has_avatar_ai": _has_avatar("ai"),
        "has_avatar_user": _has_avatar("user"),
        "feishu_connected": _feishu_bot.is_connected if _feishu_bot else False,
    }


@app.post("/api/config")
async def update_config(body: dict):
    global _config
    for k in ("mbti", "persona", "model", "api_base", "api_key", "max_steps", "workspace"):
        if k in body:
            _config[k] = body[k]
    # 下次请求时自动重建 agent
    global _agent_ref
    _agent_ref = None

    # 处理飞书配置变更
    feishu_changed = False
    for k in ("feishu_app_id", "feishu_app_secret", "feishu_enabled"):
        if k in body:
            _config[k] = body[k]
            feishu_changed = True

    if feishu_changed:
        _stop_feishu_bot()
        _start_feishu_bot()

    return {"status": "ok", "config": _config}


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


# WebSocket — 对话
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            user_text = msg.get("message", "").strip()
            if not user_text:
                continue

            # 发送"正在输入"状态
            await ws.send_json({"type": "status", "content": "thinking"})

            # 获取 agent 并执行
            try:
                wrapper = _get_or_create_agent()
                response = await wrapper.run(user_text)
                if response and not response.startswith("LLM call failed"):
                    await ws.send_json({"type": "message", "content": response})
                else:
                    await ws.send_json({"type": "error", "content": "抱歉，我出神了没听清… 能再说一遍吗？"})
            except Exception as e:
                logging.getLogger("companion").error(f"WebSocket 错误: {e}", exc_info=True)
                await ws.send_json({"type": "error", "content": "抱歉，我出错了… 请稍后再试。"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# 静态文件
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
