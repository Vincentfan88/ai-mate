"""日记插件 — AI 伴侣可以写日记，用户可以阅读，并支持推送到飞书文档。"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from mini_agent.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


# ── 飞书文档推送（轻量级，不依赖 SDK）─────────────────────────

class FeishuDocPusher:
    """将日记内容推送到飞书文档。使用 httpx 直接调用 API。"""

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret
        self._token: Optional[str] = None
        self._token_expire: float = 0

    async def _ensure_token(self, client) -> str:
        """获取或刷新 tenant_access_token。"""
        import time
        now = time.time()
        if self._token and now < self._token_expire - 300:
            return self._token

        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")
        self._token = data["tenant_access_token"]
        self._token_expire = now + data.get("expire", 7200)
        return self._token

    async def push(self, title: str, date: str, content: str, mood: str = "", chat_id: str = "") -> str:
        """创建飞书文档并写入内容，返回文档 URL。

        Args:
            title: 文档标题
            date: 日期 YYYY-MM-DD
            content: 日记正文
            mood: 当日心情
            chat_id: 飞书会话 ID（如果提供，会发送一条通知消息）

        Returns:
            文档 URL，格式为 https://feishu.cn/docx/{doc_id}
        """
        import re
        import httpx

        async with httpx.AsyncClient() as client:
            token = await self._ensure_token(client)

            # 1. 创建文档
            resp = await client.post(
                "https://open.feishu.cn/open-apis/docx/v1/documents",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": title},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"创建文档失败: {data.get('msg')}")
            doc_id = data["data"]["document"]["document_id"]
            doc_url = f"https://feishu.cn/docx/{doc_id}"

            # 等待文档就绪
            import asyncio
            await asyncio.sleep(1)

            # 2. 构建内容块
            children = []

            # 日期/心情信息行
            children.append({
                "block_type": 2,
                "text": {
                    "style": {},
                    "elements": [
                        {
                            "text_run": {
                                "content": f"日期：{date}  情绪：{mood}" if mood else f"日期：{date}",
                                "text_element_style": {"italic": True},
                            }
                        }
                    ],
                },
            })

            # 分隔线
            children.append({
                "block_type": 2,
                "text": {
                    "style": {},
                    "elements": [
                        {"text_run": {"content": "─" * 30, "text_element_style": {}}}
                    ],
                },
            })

            # 正文段落（按句号拆分）
            sentences = re.split(r"(?<=[。！？\n])", content)
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    children.append({
                        "block_type": 2,
                        "text": {
                            "style": {},
                            "elements": [
                                {"text_run": {"content": sent, "text_element_style": {}}}
                            ],
                        },
                    })

            # 3. 写入内容（doc_id 作为 parent block_id）
            resp = await client.post(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers={"Authorization": f"Bearer {token}"},
                json={"children": children},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"写入内容失败: {data.get('msg')}")

            # 4. 可选：发送通知消息
            if chat_id:
                await self._send_notification(client, token, chat_id, title, doc_url, date)

            return doc_url

    async def _send_notification(self, client, token: str, chat_id: str, title: str, doc_url: str, date: str):
        """发送通知消息到飞书。"""
        msg_text = f"📔 新日记已创建\n日期：{date}\n点击查看：{doc_url}"
        content = json.dumps({"text": msg_text})
        try:
            await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": content,
                },
            )
        except Exception as e:
            logger.warning(f"[Diary] 飞书通知发送失败: {e}")


@dataclass
class DiaryEntry:
    """一条日记"""
    id: str
    date: str            # YYYY-MM-DD
    content: str         # 正文
    mood: str = ""       # 当日心情
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DiaryEntry":
        return cls(**d)


class CompanionDiaryTool(Tool):
    """写日记/读日记/推送飞书文档 — 供 AI 伴侣使用。"""

    def __init__(self, workspace: str, feishu_app_id: str = "", feishu_app_secret: str = "", feishu_chat_id: str = ""):
        self._diary_path = Path(workspace) / "diary"
        self._diary_path.mkdir(parents=True, exist_ok=True)
        self._state_file = self._diary_path / "entries.json"
        self._entries: List[DiaryEntry] = []
        self._load()

        # Feishu docs pusher (optional)
        self._feishu_pusher: Optional[FeishuDocPusher] = None
        self._feishu_chat_id = feishu_chat_id
        if feishu_app_id and feishu_app_secret:
            self._feishu_pusher = FeishuDocPusher(feishu_app_id, feishu_app_secret)

    def _load(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._entries = [DiaryEntry.from_dict(d) for d in data]
            except Exception as e:
                logger.warning(f"[Diary] 加载失败: {e}")

    def _save(self):
        self._state_file.write_text(
            json.dumps([e.to_dict() for e in self._entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def name(self) -> str:
        return "companion_diary"

    @property
    def description(self) -> str:
        desc = (
            "写日记或读日记。每天可以写一篇日记记录感受和想法，"
            "也可以回顾之前的日记。在你想记录今天的心情或回顾过去时使用。"
            "写完日记后，可以用 push_to_feishu 动作将日记推送到飞书文档。"
        )
        return desc

    @property
    def parameters(self) -> dict:
        actions = ["write", "read", "recent", "push_to_feishu"]
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": actions,
                    "description": "操作类型：write=写日记，read=读指定日期的日记，recent=看最近几篇，push_to_feishu=推送日记到飞书文档",
                },
                "content": {
                    "type": "string",
                    "description": "日记内容（action=write 时必需）",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD（action=read 时必需，push_to_feishu 时可选，不传则推送最新一篇）",
                },
                "mood": {
                    "type": "string",
                    "description": "当日心情（write 时可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回最近篇数（action=recent 时使用，默认3）",
                },
                "title": {
                    "type": "string",
                    "description": "文档标题（push_to_feishu 时可选，默认为'AI日记 - 日期'）",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        content: str = "",
        date: str = "",
        mood: str = "",
        limit: int = 3,
        title: str = "",
    ) -> ToolResult:
        try:
            if action == "write":
                if not content:
                    return ToolResult(success=False, content="", error="写日记需要提供 content")
                today = datetime.now().strftime("%Y-%m-%d")
                # 检查今天是否已写过
                existing = [e for e in self._entries if e.date == today]
                if existing:
                    return ToolResult(
                        success=False,
                        content="",
                        error=f"今天已经写过日记了（{today}），明天再来吧",
                    )
                entry = DiaryEntry(
                    id=f"diary_{len(self._entries)}_{datetime.now().strftime('%Y%m%d')}",
                    date=today,
                    content=content,
                    mood=mood,
                )
                self._entries.append(entry)
                self._save()
                return ToolResult(success=True, content=f"日记已保存（{today}）")

            elif action == "read":
                if not date:
                    return ToolResult(success=False, content="", error="读日记需要提供 date (YYYY-MM-DD)")
                for entry in self._entries:
                    if entry.date == date:
                        mood_text = f"\n心情：{entry.mood}" if entry.mood else ""
                        return ToolResult(
                            success=True,
                            content=f"📔 {date}{mood_text}\n{entry.content}",
                        )
                return ToolResult(success=True, content=f"{date} 没有日记记录")

            elif action == "recent":
                if not self._entries:
                    return ToolResult(success=True, content="还没有写过日记")
                recent = sorted(self._entries, key=lambda e: e.date, reverse=True)[:limit]
                lines = []
                for entry in recent:
                    mood_text = f" [{entry.mood}]" if entry.mood else ""
                    preview = entry.content[:50] + ("..." if len(entry.content) > 50 else "")
                    lines.append(f"- {entry.date}{mood_text}: {preview}")
                return ToolResult(
                    success=True,
                    content=f"最近 {len(recent)} 篇日记:\n" + "\n".join(lines),
                )

            elif action == "push_to_feishu":
                if not self._feishu_pusher:
                    return ToolResult(
                        success=False, content="",
                        error="飞书文档推送未配置（缺少 app_id / app_secret）",
                    )
                # 查找目标日记
                target = None
                if date:
                    for entry in self._entries:
                        if entry.date == date:
                            target = entry
                            break
                    if not target:
                        return ToolResult(success=False, content="", error=f"未找到 {date} 的日记")
                else:
                    # 取最新一篇
                    if not self._entries:
                        return ToolResult(success=True, content="还没有写过日记")
                    target = sorted(self._entries, key=lambda e: e.date, reverse=True)[0]

                doc_title = title if title else f"AI日记 - {target.date}"
                try:
                    doc_url = await self._feishu_pusher.push(
                        title=doc_title,
                        date=target.date,
                        content=target.content,
                        mood=target.mood,
                        chat_id=self._feishu_chat_id,
                    )
                    return ToolResult(
                        success=True,
                        content=f"日记已推送到飞书文档并发送通知：{doc_url}",
                    )
                except RuntimeError as e:
                    return ToolResult(success=False, content="", error=str(e))

            else:
                return ToolResult(success=False, content="", error=f"未知动作: {action}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"日记操作失败: {e}")


def register(registry) -> list[Tool]:
    """插件入口点 — 返回该插件提供的 Tool 列表。"""
    import os
    feishu_app_id = os.environ.get("FEISHU_APP_ID", "")
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    feishu_chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    # If not in env, try loading from config.json
    if not feishu_app_id or not feishu_app_secret:
        try:
            config_path = Path(__file__).parents[3] / "workspace" / "companion" / "config.json"
            if config_path.exists():
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                feishu_app_id = feishu_app_id or cfg.get("feishu_app_id", "")
                feishu_app_secret = feishu_app_secret or cfg.get("feishu_app_secret", "")
                feishu_chat_id = feishu_chat_id or cfg.get("feishu_chat_id", "")
        except Exception:
            pass
    return [CompanionDiaryTool(workspace=registry.workspace, feishu_app_id=feishu_app_id, feishu_app_secret=feishu_app_secret, feishu_chat_id=feishu_chat_id)]


def get_info() -> dict:
    """插件元信息。"""
    return {
        "name": "diary",
        "version": "0.1.0",
        "description": "AI 伴侣日记 — 写日记和阅读功能",
    }