"""
触发引擎 - Trigger Engine

管理 AI 伴侣主动联系用户的触发逻辑。
"""

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable


class TriggerCandidate:
    """触发候选数据类"""

    def __init__(self, trigger_type: str, priority: float = 0.5, data: Optional[Dict] = None):
        self.trigger_type = trigger_type
        self.priority = priority
        self.data = data or {}
        self.timestamp = datetime.now()


class WeibullGenerator:
    """Weibull 分布随机数生成器"""

    def __init__(self, alpha: float = 1.5, beta: float = 12.0):
        """
        Args:
            alpha: 形状参数 (影响分布形态)
            beta: 尺度参数 (平均间隔时间，小时)
        """
        self.alpha = alpha
        self.beta = beta

    def generate_interval(self) -> float:
        """生成 Weibull 分布的间隔时间 (小时)"""
        u = random.random()
        return self.beta * (-math.log(u)) ** (1 / self.alpha)

    def schedule_next_contact(self, from_time: Optional[datetime] = None) -> datetime:
        """安排下次联系时间"""
        interval = self.generate_interval()
        base_time = from_time or datetime.now()
        return base_time + timedelta(hours=interval)


class HMMState:
    """HMM 隐马尔可夫模型状态"""

    IDLE = "idle"
    ACTIVE_CONVERSATION = "active_conversation"
    MISSING_USER = "missing_user"
    SHARE_MOMENT = "share_moment"
    CHECK_IN = "check_in"


class TriggerEngine:
    """多层触发引擎"""

    # 类级别配置缓存（首次加载后缓存）
    _config_loaded: bool = False

    def __init__(
        self,
        weibull_generator: WeibullGenerator,
        on_trigger: Callable[[TriggerCandidate], None],
        can_contact: Optional[Callable[[], bool]] = None,
        should_skip: Optional[Callable[[], bool]] = None,
        config_dir: str = "./config",
    ):
        """
        Args:
            weibull_generator: Weibull 时间生成器
            on_trigger: 触发回调函数
            can_contact: 检查是否可以联系的钩子
            should_skip: 检查应该跳过的钩子
            config_dir: 配置文件目录
        """
        self.weibull_gen = weibull_generator
        self.on_trigger = on_trigger
        self.can_contact = can_contact or (lambda: True)
        self.should_skip = should_skip or (lambda: False)

        self.last_contact: Optional[datetime] = None
        self.next_scheduled_time: Optional[datetime] = None
        self.current_state = HMMState.IDLE

        # 实例级硬规则配置（默认凌晨 0-6 点勿扰，最小间隔 4 小时）
        self.quiet_hours: List[int] = list(range(0, 7))
        self.min_hours_between_contacts: float = 4.0

        # 从 YAML 配置加载
        if not hasattr(self, '_config_loaded'):
            self._load_config(config_dir)

    def _load_config(self, config_dir: str) -> None:
        """从配置加载硬过滤参数"""
        try:
            from core.utils.config_loader import get_loader

            loader = get_loader(config_dir)
            default_config = loader.load_default()
            hard_filter = default_config.get("hard_filter", {})
            self.quiet_hours = hard_filter.get("quiet_hours", list(range(0, 7)))
            self.min_hours_between_contacts = hard_filter.get("min_interval_hours", 4.0)
            self._config_loaded = True
        except Exception:
            logger.warning(f"[触发器] 配置加载失败，使用默认值: {e}")
            return
        if not hasattr(TriggerEngine, '_config_loaded'):
            TriggerEngine._config_loaded = True

    def start(self) -> None:
        """启动触发引擎"""
        self._schedule_next_contact()

    def _schedule_next_contact(self) -> None:
        """安排下次联系"""
        self.next_scheduled_time = self.weibull_gen.schedule_next_contact(self.last_contact)

    def check_cycle(self) -> Optional[TriggerCandidate]:
        """主检查循环"""
        now = datetime.now()

        # 第 1 层：硬规则过滤
        if not self._layer1_hard_rules(now):
            return None

        # 第 2 层：结构化查询
        candidate = self._layer2_query()
        if candidate is None:
            # Weibull 时机检查
            if not self._check_weibull_timing(now):
                return None
            candidate = TriggerCandidate("spontaneous", priority=0.5)

        # 第 3 层：状态计算
        state_info = self._layer3_state_calculation()
        candidate.priority = state_info.get("priority", 0.5)

        # 执行触发
        self.on_trigger(candidate)
        self.last_contact = now
        self._schedule_next_contact()

        return candidate

    def _layer1_hard_rules(self, now: datetime) -> bool:
        """第 1 层：硬规则过滤"""
        # 检查最后联系时间
        if self.last_contact:
            hours_since = (now - self.last_contact).total_seconds() / 3600
            if hours_since < self.min_hours_between_contacts:
                return False

        # 检查安静时段
        if now.hour in self.quiet_hours:
            return False

        return self.can_contact()

    def _layer2_query(self) -> Optional[TriggerCandidate]:
        """第 2 层：结构化查询"""
        # 可扩展：检查日期触发事件、纪念日等
        return None

    def _layer3_state_calculation(self) -> Dict:
        """第 3 层：状态计算"""
        # 简化版状态计算
        if self.last_contact:
            hours_since = (datetime.now() - self.last_contact).total_seconds() / 3600
            missing_level = min(1.0, hours_since / 48)
        else:
            missing_level = 0.5

        return {
            "current_state": HMMState.MISSING_USER if missing_level > 0.7 else HMMState.IDLE,
            "missing_level": missing_level,
            "priority": 0.3 + missing_level * 0.4
        }

    def _check_weibull_timing(self, now: datetime) -> bool:
        """检查 Weibull 间隔是否到达"""
        if self.next_scheduled_time is None:
            return False
        return now >= self.next_scheduled_time
