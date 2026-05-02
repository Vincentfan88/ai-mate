"""MD 对话日志 — 按日期存储全量对话"""

import glob
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List

from .store import ConversationLog

logger = logging.getLogger(__name__)


class MdConversationLog(ConversationLog):
    """全量对话日志 — MD 格式，按日期归档"""

    def __init__(self, log_dir: str = "workspace/companion/conversations", ai_name: str = "AI"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.ai_name = ai_name

    def append(self, role: str, content: str, timestamp: str = None) -> None:
        """追加对话到当日 MD 文件"""
        ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
        date_str = ts.strftime("%Y-%m-%d")
        time_str = ts.strftime("%H:%M")
        file_path = self.log_dir / f"{date_str}.md"

        # 新文件写标题
        if not file_path.exists():
            file_path.write_text(f"# {date_str} 对话记录\n\n", encoding="utf-8")

        role_label = "User" if role == "user" else self.ai_name
        entry = f"## {time_str}\n**{role_label}**: {content}\n\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def append_note(self, note: str, timestamp: str = None) -> None:
        """追加注释（记忆提取/情绪等）"""
        ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
        date_str = ts.strftime("%Y-%m-%d")
        file_path = self.log_dir / f"{date_str}.md"

        note_entry = f"> [记录] {note}\n\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(note_entry)

    def get_recent(self, limit: int = 3) -> List[dict]:
        """获取最近 N 轮对话"""
        all_entries = []
        files = sorted(self.log_dir.glob("*.md"))
        # 从最新文件往前读，直到收集够 limit 条
        max_files = min(len(files), 30)  # 最多读 30 天
        for file_path in reversed(files[-max_files:]):
            content = file_path.read_text(encoding="utf-8")
            entries = self._parse_md(content)
            all_entries = entries + all_entries
            if len(all_entries) >= limit:
                break

        return all_entries[-limit:]

    def _parse_md(self, content: str) -> List[dict]:
        """解析 MD 格式为结构化对话"""
        entries = []
        # 匹配 "## HH:MM\n**User/{ai_name}**: 内容"
        pattern = re.compile(
            rf"## (\d{{2}}:\d{{2}})\n\*\*(User|{re.escape(self.ai_name)})\*\*: (.+?)(?=\n\n|\n##|$)",
            re.DOTALL,
        )
        for match in pattern.finditer(content):
            time_str, role_label, text = match.groups()
            role = "user" if role_label == "User" else "assistant"
            entries.append({
                "role": role,
                "content": text.strip(),
                "time": time_str,
            })
        return entries
