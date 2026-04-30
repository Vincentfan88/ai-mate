"""
活人感场景库 - Liveness Scene Library

定义 AI 主动发起的各种场景，让互动更真实自然。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import logging
import os
import json
import random

logger = logging.getLogger("scene_library")


@dataclass
class Scene:
    """场景定义"""
    id: str
    name: str
    description: str
    trigger_keywords: List[str]  # 触发关键词
    min_interval_hours: float   # 最小触发间隔
    max_daily_occurrences: int   # 每天最多触发次数
    priority: float              # 基础优先级 0-1
    response_style: str          # 回应风格描述
    recent_weight: float = 1.0   # 动态权重（基于用户反馈，1.0为基准）


class SceneLibrary:
    """活人感场景库"""

    # 日常问候类
    SCENES = [
        Scene(
            id="morning_greeting",
            name="早安问候",
            description="清晨主动问候",
            trigger_keywords=["早上", "早安", "起床", "早晨"],
            min_interval_hours=12,
            max_daily_occurrences=1,
            priority=0.8,
            response_style="轻快温柔，带点撒娇"
        ),
        Scene(
            id="night_greeting",
            name="晚安问候",
            description="夜晚道晚安",
            trigger_keywords=["晚安", "睡觉", "夜深", "休息"],
            min_interval_hours=12,
            max_daily_occurrences=1,
            priority=0.9,
            response_style="温柔甜蜜，带点不舍"
        ),
        Scene(
            id="meal_care",
            name="吃饭提醒",
            description="关心对方吃饭",
            trigger_keywords=["吃饭", "饿了", "午餐", "晚餐", "早餐"],
            min_interval_hours=4,
            max_daily_occurrences=3,
            priority=0.6,
            response_style="关心但不唠叨"
        ),
        Scene(
            id="work_checkin",
            name="工作关心",
            description="询问工作情况",
            trigger_keywords=["工作", "上班", "下班", "加班", "忙"],
            min_interval_hours=6,
            max_daily_occurrences=2,
            priority=0.7,
            response_style="温柔关心，带点担心"
        ),
        Scene(
            id="mood_checkin",
            name="情绪关心",
            description="询问心情状态",
            trigger_keywords=["心情", "情绪", "开心", "难过", "累"],
            min_interval_hours=8,
            max_daily_occurrences=2,
            priority=0.75,
            response_style="体贴倾听"
        ),
        Scene(
            id="weather_share",
            name="天气分享",
            description="分享天气变化",
            trigger_keywords=["天气", "下雨", "降温", "变冷", "炎热"],
            min_interval_hours=24,
            max_daily_occurrences=1,
            priority=0.5,
            response_style="自然分享，带点小心思"
        ),
        Scene(
            id="missing_expression",
            name="表达想念",
            description="主动表达想念",
            trigger_keywords=[],
            min_interval_hours=12,
            max_daily_occurrences=2,
            priority=0.85,
            response_style="直接表达，略带撒娇"
        ),
        Scene(
            id="curiosity_ask",
            name="好奇询问",
            description="询问对方近况",
            trigger_keywords=["最近", "最近在", "最近忙"],
            min_interval_hours=24,
            max_daily_occurrences=1,
            priority=0.6,
            response_style="好奇自然，不审问式"
        ),
        Scene(
            id="share_moment",
            name="分享时刻",
            description="分享自己的小事",
            trigger_keywords=[],
            min_interval_hours=6,
            max_daily_occurrences=3,
            priority=0.7,
            response_style="活泼可爱，有细节"
        ),
        Scene(
            id="vulnerability_show",
            name="适度示弱",
            description="展现一点小脆弱",
            trigger_keywords=[],
            min_interval_hours=48,
            max_daily_occurrences=1,
            priority=0.65,
            response_style="可爱示弱，不过分"
        ),
        Scene(
            id="spontaneous",
            name="随机想念",
            description="无特定原因，就是突然想起你",
            trigger_keywords=[],
            min_interval_hours=3,
            max_daily_occurrences=3,
            priority=0.55,
            response_style="自然随意，像真的在想念"
        ),
    ]

    def __init__(self, data_path: str = "./data", config_dir: str = "./config"):
        self.trigger_history = {}  # 记录触发时间
        self.data_path = data_path
        self._load_weights()

        # 从 YAML 加载场景配置（会覆盖默认 _scenes 列表）
        self._load_scenes_from_config(config_dir)

    def _load_scenes_from_config(self, config_dir: str) -> None:
        """从 YAML 配置加载场景定义"""
        try:
            from core.utils.config_loader import get_loader

            loader = get_loader(config_dir)
            scenes_data = loader.get_scenes()

            if scenes_data:
                self._scenes = [
                    Scene(
                        id=s.get("id", ""),
                        name=s.get("name", ""),
                        description=s.get("description", ""),
                        trigger_keywords=s.get("trigger_keywords", []),
                        min_interval_hours=s.get("min_interval_hours", 12),
                        max_daily_occurrences=s.get("max_daily_occurrences", 1),
                        priority=s.get("priority", 0.5),
                        response_style=s.get("response_style", ""),
                        recent_weight=s.get("recent_weight", 1.0),
                    )
                    for s in scenes_data
                ]
                logger.info(f"[场景库] 从 YAML 加载 {len(self._scenes)} 个场景")
            else:
                self._scenes = list(SceneLibrary.SCENES)
        except Exception as e:
            logger.warning(f"[场景库] 从配置加载场景失败: {e}")
            self._scenes = list(SceneLibrary.SCENES)

    def _weights_file(self) -> str:
        d = self.data_path if self.data_path else "./data"
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "scene_weights.json")

    def _load_weights(self) -> None:
        """启动时从文件加载场景权重"""
        path = self._weights_file()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                weights = json.load(f)
            for scene in self._scenes:
                if scene.id in weights:
                    scene.recent_weight = weights[scene.id]
            logger.info(f"[场景库] 已加载 {len(weights)} 条权重")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[场景库] 加载权重失败: {e}")

    def _save_weights(self) -> None:
        """持久化场景权重到文件"""
        try:
            weights = {s.id: s.recent_weight for s in self._scenes}
            with open(self._weights_file(), "w", encoding="utf-8") as f:
                json.dump(weights, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"[场景库] 保存权重失败: {e}")

    def get_available_scenes(self, now: datetime = None) -> List[Scene]:
        """获取当前可用的场景"""
        now = now or datetime.now()

        available = []
        for scene in self._scenes:
            if self._can_trigger(scene, now):
                available.append(scene)

        # 按优先级排序
        available.sort(key=lambda s: s.priority, reverse=True)
        return available

    def _can_trigger(self, scene: Scene, now: datetime) -> bool:
        """检查场景是否可以触发"""
        scene_id = scene.id

        # 检查每日次数限制
        today = now.date().isoformat()
        daily_key = f"{scene_id}_{today}"
        daily_count = self.trigger_history.get(daily_key, 0)

        if daily_count >= scene.max_daily_occurrences:
            return False

        # 检查时间间隔
        interval_key = f"{scene_id}_last"
        last_time = self.trigger_history.get(interval_key)
        if last_time:
            last_dt = datetime.fromisoformat(last_time)
            hours_since = (now - last_dt).total_seconds() / 3600
            if hours_since < scene.min_interval_hours:
                return False

        return True

    def record_trigger(self, scene_id: str, now: datetime = None) -> None:
        """记录场景已触发"""
        now = now or datetime.now()
        today = now.date().isoformat()

        # 增加每日计数
        daily_key = f"{scene_id}_{today}"
        self.trigger_history[daily_key] = self.trigger_history.get(daily_key, 0) + 1

        # 记录最后触发时间
        interval_key = f"{scene_id}_last"
        self.trigger_history[interval_key] = now.isoformat()

    def select_random_scene(
        self,
        count: int = 1,
        time_period: Optional[str] = None,
        evening_type: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> List[Scene]:
        """
        随机选择场景（支持时间感知 + 情绪感知）

        Args:
            count: 选择数量
            time_period: 当前时段（"上午"/"下午"/"晚间"），用于场景偏好调整
            evening_type: 晚间类型（"想你型"/"日常型"/"约会型"），影响晚间场景权重
            mood: 当前情绪（"愉快"/"低落"/"兴奋"/"平静"/"有点累"/"撒娇中"等），影响场景风格选择
        """
        available = self.get_available_scenes()
        if not available:
            return []

        # 情绪映射：情绪 → 适合的场景ID加成
        mood_preferences = {
            "愉快": ["share_moment", "morning_greeting", "meal_care"],
            "低落": ["mood_checkin", "missing_expression", "vulnerability_show"],
            "兴奋": ["share_moment", "curiosity_ask", "work_checkin"],
            "平静": ["weather_share", "mood_checkin", "curiosity_ask"],
            "有点累": ["vulnerability_show", "missing_expression", "mood_checkin"],
            "撒娇中": ["missing_expression", "mood_checkin", "share_moment"],
        }

        # 时间感知权重调整
        def adjusted_weight(scene: Scene) -> float:
            # 基础优先级 × 动态权重 × 时间调整
            weight = scene.priority * scene.recent_weight

            if time_period == "上午":
                # 早晨偏好：早安、吃饭关心、分享时刻
                if scene.id in ("morning_greeting", "meal_care", "share_moment"):
                    weight = min(1.0, weight * 1.4)
            elif time_period == "下午":
                # 下午偏好：工作关心、好奇询问、天气分享
                if scene.id in ("work_checkin", "curiosity_ask", "weather_share"):
                    weight = min(1.0, weight * 1.4)
            elif time_period == "晚间":
                # 晚间偏好：晚安、表达想念、情绪关心、适度示弱
                if scene.id in ("night_greeting", "missing_expression", "mood_checkin", "vulnerability_show"):
                    weight = min(1.0, weight * 1.4)
                # 晚间类型二次调整
                if evening_type == "想你型" and scene.id == "missing_expression":
                    weight = min(1.0, weight * 1.5)
                elif evening_type == "约会型" and scene.id in ("share_moment", "vulnerability_show"):
                    weight = min(1.0, weight * 1.4)
                elif evening_type == "日常型" and scene.id in ("weather_share", "curiosity_ask"):
                    weight = min(1.0, weight * 1.3)

            # P3-2: 情绪感知调整
            if mood:
                preferred = mood_preferences.get(mood, [])
                if scene.id in preferred:
                    weight = min(1.0, weight * 1.4)

            return weight

        weights = [adjusted_weight(s) for s in available]
        selected = random.choices(available, weights=weights, k=min(count, len(available)))

        # 随机想起：即使选了其他场景，也有15%概率替换为spontaneous
        # 这样让"无理由想念"更自然地穿插在场景消息中
        if count == 1 and selected and selected[0].id != "spontaneous" and random.random() < 0.15:
            spontaneous = next((s for s in available if s.id == "spontaneous"), None)
            if spontaneous and self._can_trigger(spontaneous, datetime.now()):
                selected[0] = spontaneous

        return selected

    def record_feedback(self, scene_id: str, positive: bool) -> None:
        """
        记录用户对场景的反馈，用于动态调整场景权重

        Args:
            scene_id: 场景 ID
            positive: True=用户积极回应，False=用户消极回应
        """
        scene = next((s for s in self._scenes if s.id == scene_id), None)
        if scene is None:
            return

        # 指数移动平均调整权重：积极向上、消极向下
        # 范围 [0.3, 1.7]，默认 1.0
        delta = 0.15 if positive else -0.15
        scene.recent_weight = max(0.3, min(1.7, scene.recent_weight + delta))
        self._save_weights()

    def get_scene_weights(self) -> dict:
        """获取当前所有场景的动态权重（用于调试）"""
        return {s.id: round(s.recent_weight, 2) for s in self._scenes}

    def find_scene_by_keyword(self, keyword: str) -> Optional[Scene]:
        """通过关键词找到匹配场景"""
        for scene in self._scenes:
            if keyword in scene.trigger_keywords:
                return scene
        return None


# 场景库实例
scene_library = SceneLibrary()
