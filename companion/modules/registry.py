"""Companion 模块注册表 — 统一管理所有模块实例。"""

from datetime import datetime
from typing import Any, Dict, Optional

from companion.modules.memory import MemorySystem
from companion.modules.memory.flashback import FlashbackEngine
from companion.modules.emotion import EmotionSystem
from companion.modules.trigger import TriggerEngine
from companion.modules.mbti import MBTIAdapter
from companion.modules.scene import SceneLibrary
from companion.modules.liveness import LivenessTracker
from companion.modules.extras import HabitTracker, TrendingCache
from companion.modules.extras.time_awareness import TimeAwareness


class CompanionRegistry:
    """Companion 模块注册表"""

    def __init__(
        self,
        workspace: str = "workspace/companion",
        config_dir: str = "companion/config",
        mbti_type: str = "ENFP",
        persona_name: str = "default",
        persona_path: Optional[str] = None,
        trigger_quiet_hours: tuple = None,
    ):
        self._base_workspace = workspace
        self.workspace = f"{workspace}/{persona_name}"
        self.config_dir = config_dir
        self.mbti_type = mbti_type
        self._persona_name = persona_name
        self._persona_path = persona_path
        self._trigger_overrides = {
            "quiet_hours": trigger_quiet_hours,
        }

        # Lazy-initialized modules
        self._modules: Dict[str, object] = {}

        # Optional LLM client for preference inference
        self._llm_client: Any = None

    def set_llm_client(self, client: Any) -> None:
        """注入 LLM 客户端（用于偏好推断等智能功能）"""
        self._llm_client = client

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def memory(self) -> MemorySystem:
        mem = self._get_or_create("memory", lambda: MemorySystem(
            workspace=self.workspace,
            persona_path=self._persona_path,
        ))
        # 如果已有 LLM 客户端，注入到 memory 系统
        if self._llm_client:
            mem.set_llm_client(self._llm_client)
        # 将 persona 名字注入到对话日志
        persona = mem.persona
        ai_name = persona.get("name", "AI") if persona else "AI"
        mem.conversation_log.ai_name = ai_name
        return mem

    @property
    def flashback(self) -> FlashbackEngine:
        return self._get_or_create("flashback", lambda: FlashbackEngine(
            memory_store=self.memory.fact_store,
        ))

    @property
    def emotion(self) -> EmotionSystem:
        return self._get_or_create("emotion", lambda: self._create_emotion_system())

    def _create_emotion_system(self) -> EmotionSystem:
        # Inject MBTI emotional config for personality-aware emotion selection
        mbti_profile = self.mbti.get_profile(self.mbti_type)
        emotional_config = {
            "primary_emotions": mbti_profile.emotional.primary_emotions,
            "emotion_triggers": mbti_profile.emotional.emotion_triggers,
            "self_disclosure_tendency": mbti_profile.emotional.self_disclosure_tendency,
        }
        return EmotionSystem(
            config_path=f"{self.config_dir}/emotions.json",
            state_file=f"{self.workspace}/states/emotion_state.json",
            emotional_config=emotional_config,
        )

    @property
    def trigger(self) -> TriggerEngine:
        return self._get_or_create("trigger", lambda: TriggerEngine(
            config_path=f"{self.config_dir}/triggers.json",
            state_path=f"{self.workspace}/states/trigger_state.json",
            quiet_hours=self._trigger_overrides.get("quiet_hours"),
        ))

    @property
    def mbti(self) -> MBTIAdapter:
        return self._get_or_create("mbti", lambda: MBTIAdapter())

    @property
    def scenes(self) -> SceneLibrary:
        return self._get_or_create("scenes", lambda: SceneLibrary(
            config_path=f"{self.config_dir}/scenes.json",
        ))

    @property
    def liveness(self) -> LivenessTracker:
        return self._get_or_create("liveness", lambda: LivenessTracker(
            data_path=f"{self.workspace}/states/liveness.json",
        ))

    @property
    def time_awareness(self) -> TimeAwareness:
        """统一时间管理 — 包含时间事件 + 纪念日（合并后的 TemporalManager）"""
        return self._get_or_create("time_awareness", lambda: TimeAwareness(
            state_path=f"{self.workspace}/states/temporal_events.json",
        ))

    @property
    def habits(self) -> HabitTracker:
        return self._get_or_create("habits", lambda: HabitTracker(
            config_path=f"{self.config_dir}/habits.json",
            state_path=f"{self.workspace}/states/habits.json",
        ))

    @property
    def trending(self) -> TrendingCache:
        return self._get_or_create("trending", lambda: TrendingCache(
            cache_path=f"{self.workspace}/trending_cache.json",
        ))

    def _get_or_create(self, name: str, factory):
        if name not in self._modules:
            self._modules[name] = factory()
        return self._modules[name]

    def get_module(self, name: str) -> Optional[object]:
        return self._modules.get(name)

    # ── Shared resource paths (not per-persona) ─────────────

    @property
    def avatar_dir(self) -> str:
        return f"{self._base_workspace}/avatars"

    # ── HMM / HardFilter 便捷通知 ───────────────────────────────

    def on_user_message(self, now: Optional[datetime] = None) -> None:
        """通知 HMM 用户发来消息（切换到 ACTIVE 状态），更新 pride + 降低 connection。"""
        self.trigger.on_user_message(now)

    def exit_conversation(self) -> str:
        """通知 HMM 对话结束（概率转移），返回新的状态名。"""
        return self.trigger.hmm.exit_conversation()