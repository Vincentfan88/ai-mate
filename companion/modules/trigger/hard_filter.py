"""硬规则过滤器模块 — 安静时段 / 外部可达性。"""

from datetime import datetime
from typing import List, Optional, Tuple


class HardFilter:
    """硬规则过滤器 — 第 1 层过滤"""

    def __init__(
        self,
        quiet_hours: tuple = (0, 6),
        externally_accessible: bool = True,
    ):
        # 兼容旧版单时间段和新版多时间段
        if isinstance(quiet_hours, tuple) and len(quiet_hours) == 2:
            self.quiet_blocks: List[Tuple[int, int]] = [quiet_hours]
        elif isinstance(quiet_hours, list):
            self.quiet_blocks = [
                (b[0], b[1]) for b in quiet_hours if isinstance(b, (list, tuple)) and len(b) == 2
            ]
        else:
            self.quiet_blocks = [(0, 6)]

        self.externally_accessible = externally_accessible

    def check(self, now: Optional[datetime] = None) -> Tuple[bool, str]:
        """检查是否满足发送条件

        Returns:
            (passed, reason)
        """
        now = now or datetime.now()

        # 规则 0: 外部可达性
        if not self.externally_accessible:
            return False, "当前不可达外部通道"

        # 规则 1: 安静时段（多段）
        if self._is_quiet_hour(now.hour):
            return False, "现在是安静时段，应该让他好好休息"

        return True, "passed"

    def _is_quiet_hour(self, hour: int) -> bool:
        """判断是否在任一安静时段内"""
        for start, end in self.quiet_blocks:
            if not start and not end:
                continue
            if start <= end:
                if start <= hour <= end:
                    return True
            else:
                # Cross midnight (e.g., 23-7)
                if hour >= start or hour <= end:
                    return True
        return False
