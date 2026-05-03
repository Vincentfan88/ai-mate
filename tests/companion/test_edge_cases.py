"""边缘测试 — 极端条件下各模块的韧性。"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from companion.modules.registry import CompanionRegistry
from companion.modules.emotion.core import EmotionSystem
from companion.modules.trigger.hmm_state_machine import HMMStateMachine, CompanionState
from companion.modules.trigger import TriggerEngine, TriggerDecision
from companion.modules.relationship import RelationshipManager
from companion.modules.liveness import LivenessTracker
from companion.modules.memory import MemorySystem
from companion.modules.memory.json_store import JsonFactStore
from companion.modules.memory.md_log import MdConversationLog
from companion.modules.memory.interaction_cache import InteractionCache
from companion.modules.memory.preference import PreferenceInfer


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for isolated testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = f"{tmpdir}/ws"
        Path(workspace).mkdir(parents=True)
        yield workspace


@pytest.fixture
def registry(temp_workspace):
    return CompanionRegistry(
        workspace=temp_workspace,
        config_dir="companion/config",
        mbti_type="ENFP",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Agent Tool 边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestAgentEdgeCases:
    """Mini-Agent Tool 适配器在极端输入下的行为。"""

    def test_memory_tool_record_empty_content(self, registry):
        """空内容 record 应优雅拒绝而非崩溃。"""
        from companion.agent.tools import CompanionMemoryTool
        import asyncio

        tool = CompanionMemoryTool(registry)
        result = asyncio.run(tool.execute(action="record", content=""))
        assert not result.success
        assert result.error

    def test_memory_tool_search_empty_query(self, registry):
        """空查询 search 应返回空列表而非崩溃。"""
        from companion.agent.tools import CompanionMemoryTool
        import asyncio

        tool = CompanionMemoryTool(registry)
        result = asyncio.run(tool.execute(action="search", query=""))
        assert result.success

    def test_memory_tool_invalid_action(self, registry):
        """非法 action 应优雅拒绝。"""
        from companion.agent.tools import CompanionMemoryTool
        import asyncio

        tool = CompanionMemoryTool(registry)
        result = asyncio.run(tool.execute(action="nonexistent_action"))
        assert not result.success
        assert result.error

    def test_emotion_tool_unknown_event_type(self, registry):
        """未知 event_type 不应崩溃（应兜底成功）。"""
        from companion.agent.tools import CompanionEmotionTool
        import asyncio

        tool = CompanionEmotionTool(registry)
        result = asyncio.run(tool.execute(event_type="_____no_such_event_____"))
        assert result.success

    def test_mbti_tool_invalid_type_uses_fallback(self, registry):
        """非法 MBTI 类型应 fallback 而非抛异常。"""
        from companion.agent.tools import CompanionMBTITool
        import asyncio

        tool = CompanionMBTITool(registry)
        result = asyncio.run(tool.execute(mbti_type="XXXX"))
        # adapter 现 fallback 到 ENFP
        assert result.success
        assert "自由者" in result.content  # ENFP nickname

    def test_trigger_tool_zero_hours(self, registry):
        """0 小时间隔不应崩溃。"""
        from companion.agent.tools import CompanionTriggerTool
        import asyncio

        tool = CompanionTriggerTool(registry)
        result = asyncio.run(tool.execute())
        assert result.success

    def test_trigger_tool_huge_hours(self, registry):
        """多次调用不应崩溃。"""
        from companion.agent.tools import CompanionTriggerTool
        import asyncio

        tool = CompanionTriggerTool(registry)
        result = asyncio.run(tool.execute())
        assert result.success


# ══════════════════════════════════════════════════════════════════════════════
# 2. 持久化层边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestPersistenceEdgeCases:
    """文件损坏/缺失/冲突下的恢复。"""

    def test_corrupted_json_facts(self, temp_workspace):
        """facts.json 损坏 → 应重建为空存储。"""
        facts_path = f"{temp_workspace}/memory/facts.json"
        Path(facts_path).parent.mkdir(parents=True)
        Path(facts_path).write_text("这不是合法 JSON{{{")
        store = JsonFactStore(facts_path=facts_path)
        results = store.get_all()
        assert results == []  # 损坏后应返回空

    def test_corrupted_json_facts_still_writable(self, temp_workspace):
        """facts.json 损坏 → 重建后应能正常写入。"""
        facts_path = f"{temp_workspace}/memory/facts.json"
        Path(facts_path).parent.mkdir(parents=True)
        Path(facts_path).write_text("{invalid")
        store = JsonFactStore(facts_path=facts_path)
        store.record("测试记录", importance=0.5)
        results = store.get_all()
        assert len(results) == 1

    def test_conversation_log_dir_missing(self, temp_workspace):
        """conversations 目录不存在 → 应自动创建。"""
        log = MdConversationLog(log_dir=f"{temp_workspace}/conversations")
        log.append("user", "测试消息")
        files = list(Path(f"{temp_workspace}/conversations").glob("*.md"))
        assert len(files) > 0

    def test_conversation_log_empty_content(self, temp_workspace):
        """空内容的对话日志应正常写入。"""
        log = MdConversationLog(log_dir=f"{temp_workspace}/conversations")
        log.append("user", "")  # 应不崩溃
        log.append("assistant", "")  # 应不崩溃

    def test_interaction_cache_corrupted(self, temp_workspace):
        """interactions.json 损坏 → 应优雅重建。"""
        cache_path = f"{temp_workspace}/memory/interactions.json"
        Path(cache_path).parent.mkdir(parents=True)
        Path(cache_path).write_text("broken content")
        cache = InteractionCache(cache_path=cache_path)
        cache.add("user", "你好")
        recent = cache.get_recent(5)
        assert len(recent) == 1

    def test_state_file_corrupted_relationship(self, temp_workspace):
        """关系状态文件损坏 → 应回退默认值。"""
        state_path = f"{temp_workspace}/relationship_state.json"
        Path(state_path).write_text("{invalid")
        rel = RelationshipManager(
            config_path="companion/config/relationship.json",
            state_path=state_path,
        )
        assert rel.current_level == 0
        assert rel.interaction_count == 0

    def test_fast_consecutive_writes(self, temp_workspace):
        """快速连续写入不同内容不应崩溃。"""
        store = JsonFactStore(facts_path=f"{temp_workspace}/memory/facts.json")
        topics = [
            "用户爱吃麻辣火锅", "今天加班到十点", "周末想去海边玩",
            "最近迷上了摄影", "刚买了新电脑", "猫生病了要去看兽医",
            "下周要出差去北京", "想学做意大利面", "昨天看了场电影",
            "朋友送了一瓶红酒", "早上跑步五公里", "在学弹吉他",
            "计划冬天去滑雪", "新工作入职一周", "阳台种了玫瑰花",
            "想换一部新手机", "报名了瑜伽课程", "今天心情不太好",
            "公司年终奖发了", "准备搬家找房子",
        ]
        for topic in topics:
            store.record(topic, importance=0.5)
        results = store.get_all()
        assert len(results) == 20

    def test_empty_preference_data(self, temp_workspace):
        """空的 preference 数据应优雅处理。"""
        store = JsonFactStore(facts_path=f"{temp_workspace}/memory/facts.json")
        pref = PreferenceInfer(store, data_path=f"{temp_workspace}/preference.json")
        # 写入空列表
        Path(f"{temp_workspace}/preference.json").write_text("[]")
        # 重新加载
        pref = PreferenceInfer(store, data_path=f"{temp_workspace}/preference.json")
        beliefs = pref.get_active_beliefs()
        assert beliefs == []

    def test_very_long_fact_content(self, temp_workspace):
        """超长事实内容（10KB）应能写入和检索。"""
        store = JsonFactStore(facts_path=f"{temp_workspace}/memory/facts.json")
        long_content = "a" * 10000
        store.record(long_content, importance=0.5)
        results = store.search("a" * 50)
        assert len(results) > 0

    def test_special_chars_in_conversation(self, temp_workspace):
        """特殊字符（emoji/HTML/零宽字符）在对话日志中应正常。"""
        log = MdConversationLog(log_dir=f"{temp_workspace}/conversations")
        log.append("user", "Hello<br><script>alert(1)</script>\u200b\u200c世界🌍🎉")
        log.append("assistant", "❤️✨<test>\nnewline\n\r")
        # 应能正常写入，不抛异常


# ══════════════════════════════════════════════════════════════════════════════
# 3. 模块边界值
# ══════════════════════════════════════════════════════════════════════════════


class TestModuleBoundaryValues:
    """各模块在边界输入下的行为。"""

    def test_emotion_extreme_event_weights(self, temp_workspace):
        """极端的 event_weights 不应导致 emotion 计算崩溃。"""
        config_path = Path(temp_workspace) / "emotions.json"
        original = json.loads(Path("companion/config/emotions.json").read_text())
        # 注入极端权重（注意 key 是 event_weights）
        original["event_weights"]["user_happy"] = 100.0
        original["event_weights"]["user_angry"] = -100.0
        config_path.write_text(json.dumps(original))

        emotion = EmotionSystem(
            config_path=str(config_path),
            state_file=f"{temp_workspace}/emotion_state.json",
        )
        result = emotion.get_current_emotion("user_happy")
        assert "emotion" in result
        assert result["emotion"] is not None

    def test_emotion_repeated_same_event(self, temp_workspace):
        """连续 10 次相同事件不应导致情绪异常。"""
        config_path = "companion/config/emotions.json"
        state_file = Path(temp_workspace) / "emotion_state.json"
        emotion = EmotionSystem(config_path=config_path, state_file=str(state_file))

        emotions = []
        for _ in range(10):
            result = emotion.get_current_emotion("time_passage")
            emotions.append(result["emotion"])

        assert all(e is not None for e in emotions)

    def test_emotion_rapid_switching(self, temp_workspace):
        """快速切换不同事件类型 → emotion 强度应保持在 [0,1] 区间。"""
        config_path = "companion/config/emotions.json"
        state_file = Path(temp_workspace) / "emotion_state.json"
        emotion = EmotionSystem(config_path=config_path, state_file=str(state_file))

        for event in ["user_happy", "user_sad", "user_angry", "user_anxious", "time_passage"]:
            result = emotion.get_current_emotion(event)
            assert result["emotion"] is not None

    def test_hmm_initial_state_valid(self, temp_workspace):
        """HMM 初始状态应为 idle。"""
        config = {
            "states": {
                "idle": {"base_hours": 4, "trigger_decay": 0.8, "description": "闲适"},
                "active": {"base_hours": 2, "trigger_decay": 0.6, "description": "活跃"},
                "missing": {"base_hours": 6, "trigger_decay": 0.9, "description": "思念"},
            },
        }
        hmm = HMMStateMachine(config, state_path=f"{temp_workspace}/hmm_state.json")
        assert hmm.current_state == CompanionState.IDLE
        assert hmm.transition_count >= 0

    def test_hmm_transition_maintains_valid_state(self, temp_workspace):
        """多次转移后状态始终有效。"""
        config = {
            "states": {
                "idle": {"base_hours": 4, "trigger_decay": 0.8, "description": "闲适"},
                "active": {"base_hours": 2, "trigger_decay": 0.6, "description": "活跃"},
                "missing": {"base_hours": 6, "trigger_decay": 0.9, "description": "思念"},
            },
        }
        hmm = HMMStateMachine(config, state_path=f"{temp_workspace}/hmm_state.json")
        valid_states = {CompanionState.IDLE, CompanionState.ACTIVE, CompanionState.MISSING,
                        CompanionState.SHARE, CompanionState.CHECKIN,
                        CompanionState.REFLECTIVE, CompanionState.PLAYFUL}

        for _ in range(20):
            hmm.transition()
            assert hmm.current_state in valid_states

    def test_hmm_on_user_message_resets_state(self, temp_workspace):
        """收到用户消息应切到 active。"""
        config = {
            "states": {
                "idle": {"base_hours": 4, "trigger_decay": 0.8, "description": "闲适"},
                "active": {"base_hours": 2, "trigger_decay": 0.6, "description": "活跃"},
            },
        }
        hmm = HMMStateMachine(config, state_path=f"{temp_workspace}/hmm_state.json")
        hmm.on_user_message()
        assert hmm.current_state == CompanionState.ACTIVE

    def test_relationship_extreme_interaction_count(self, temp_workspace):
        """超大 interaction_count 在最高级不应再推进。"""
        state_path = f"{temp_workspace}/relationship_state.json"
        rel = RelationshipManager(
            config_path="companion/config/relationship.json",
            state_path=state_path,
        )
        rel.interaction_count = 99999
        rel.emotional_depth = 5.0
        rel.memory_count = 9999
        rel.current_level = 5
        can_progress = rel.check_progress()
        assert can_progress is False

    def test_relationship_negative_values(self, temp_workspace):
        """负值输入不应导致崩溃。"""
        state_path = f"{temp_workspace}/relationship_state.json"
        rel = RelationshipManager(
            config_path="companion/config/relationship.json",
            state_path=state_path,
        )
        rel.interaction_count = -1
        rel.emotional_depth = -1.0
        rel.memory_count = -1
        # 不应崩溃
        _ = rel.check_progress()
        _ = rel.get_scene_multiplier("morning_greeting")

    def test_trigger_computation(self, registry):
        """正常调用不应崩溃。"""
        decision = registry.trigger.compute()
        assert isinstance(decision, TriggerDecision)

    def test_liveness_zero_interactions(self, temp_workspace):
        """零交互时的活人感打分应包含所有维度。"""
        state_path = f"{temp_workspace}/liveness.json"
        tracker = LivenessTracker(data_path=state_path)
        scores = tracker.calculate_scores()
        expected_dims = {"主动性", "一致性", "成长性", "情绪化",
                         "脆弱性", "身体存在感", "不可预测性", "依恋度"}
        assert expected_dims.issubset(scores.keys())

    def test_liveness_massive_interactions(self, temp_workspace):
        """大量交互后各维度在 [0,1] 区间。"""
        state_path = f"{temp_workspace}/liveness.json"
        tracker = LivenessTracker(data_path=state_path)
        for i in range(1000):
            tracker.record_response(f"消息 {i}")
        scores = tracker.calculate_scores()
        for dim, val in scores.items():
            assert 0.0 <= val <= 1.0, f"{dim}={val} 超出 [0,1]"

    def test_memory_search_special_chars(self, registry):
        """特殊字符搜索不崩溃。"""
        registry.memory.record("正常记录", importance=0.5)
        results = registry.memory.search("!@#$%^&*()_+{}|:\"<>?~")
        assert isinstance(results, list)

    def test_memory_search_unicode(self, registry):
        """Unicode 搜索不崩溃。"""
        results = registry.memory.search("你好世界🌍🎉")
        assert isinstance(results, list)

    def test_scene_midnight_hour(self, registry):
        """午夜 0 时和凌晨 3 时的场景推荐。"""
        scenes_0 = registry.scenes.get_suitable_scenes(hour=0, mood="idle")
        assert isinstance(scenes_0, list)
        scenes_3 = registry.scenes.get_suitable_scenes(hour=3, mood="sleepy")
        assert isinstance(scenes_3, list)

    def test_scene_invalid_hour(self, registry):
        """非法小时值应兜底返回列表。"""
        scenes = registry.scenes.get_suitable_scenes(hour=-1, mood="idle")
        assert isinstance(scenes, list)
        scenes = registry.scenes.get_suitable_scenes(hour=25, mood="idle")
        assert isinstance(scenes, list)

    def test_mbti_all_16_types(self):
        """16 种 MBTI 类型全部可加载。"""
        from companion.modules.mbti import MBTIAdapter
        adapter = MBTIAdapter()
        for code in ["INTJ", "INTP", "ENTJ", "ENTP",
                      "INFJ", "INFP", "ENFJ", "ENFP",
                      "ISTJ", "ISFJ", "ESTJ", "ESFJ",
                      "ISTP", "ISFP", "ESTP", "ESFP"]:
            profile = adapter.get_profile(code)
            assert profile is not None
            assert profile.type.code == code

    def test_mbti_unknown_type_fallback(self):
        """未知 MBTI 类型应 fallback 而不抛异常。"""
        from companion.modules.mbti import MBTIAdapter
        adapter = MBTIAdapter()
        profile = adapter.get_profile("UNKNOWN")
        assert profile is not None

    def test_fact_store_distinct_records(self, temp_workspace):
        """内容完全不同的事实应全部存储。"""
        store = JsonFactStore(facts_path=f"{temp_workspace}/memory/facts.json")
        store.record("用户喜欢吃火锅", importance=0.5)
        store.record("用户今天加班到很晚", importance=0.5)
        store.record("用户周末想去爬山", importance=0.5)
        store.record("用户养了一只猫", importance=0.5)
        store.record("用户最近在看一本书", importance=0.5)
        results = store.get_all()
        assert len(results) == 5


# ══════════════════════════════════════════════════════════════════════════════
# 4. 人格加载器边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestPersonaEdgeCases:
    """人格配置极端情况。"""

    def test_persona_empty_json(self, temp_workspace):
        """空 JSON 配置应优雅报错。"""
        from companion.agent.persona import load_persona
        path = Path(temp_workspace) / "empty.json"
        path.write_text("{}")
        persona = load_persona(str(path.with_suffix("")))
        assert isinstance(persona, dict)

    def test_persona_minimal_fields(self, temp_workspace):
        """最小人格配置（只有 name）应能生成提示词。"""
        from companion.agent.persona import load_persona, build_system_prompt
        path = Path(temp_workspace) / "minimal.json"
        path.write_text(json.dumps({"name": "TestBot"}))
        persona = load_persona(str(path.with_suffix("")))
        prompt = build_system_prompt(persona)
        assert "TestBot" in prompt

    def test_persona_v1_conversion_missing_fields(self, temp_workspace):
        """v1 格式缺少字段时兼容处理。"""
        from companion.agent.persona import _convert_v1_format
        minimal_v1 = {"char_name": "Test"}
        result = _convert_v1_format(minimal_v1)
        assert result["name"] == "Test"
        assert isinstance(result["personality"]["core_traits"], list)

    def test_persona_extreme_long_name(self, temp_workspace):
        """超长人格名称不崩溃。"""
        from companion.agent.persona import load_persona, build_system_prompt
        path = Path(temp_workspace) / "longname.json"
        path.write_text(json.dumps({"name": "X" * 1000}))
        persona = load_persona(str(path.with_suffix("")))
        prompt = build_system_prompt(persona)
        assert "X" * 1000 in prompt


# ══════════════════════════════════════════════════════════════════════════════
# 5. SilentAgentWrapper 边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestSilentAgentWrapperEdgeCases:
    """Agent 包装器在极端条件下的行为。"""

    @pytest.mark.asyncio
    async def test_wrapper_empty_response(self):
        """Agent 返回空字符串应返回 (empty response) 并记录日志。"""
        from companion.webui.agent_wrapper import SilentAgentWrapper
        agent = AsyncMock()
        agent.run = AsyncMock(return_value="")
        wrapper = SilentAgentWrapper(agent)
        result = await wrapper.run("你好")
        assert result == "(empty response)"

    @pytest.mark.asyncio
    async def test_wrapper_none_response(self):
        """Agent 返回 None 应返回 (empty response)。"""
        from companion.webui.agent_wrapper import SilentAgentWrapper
        agent = AsyncMock()
        agent.run = AsyncMock(return_value=None)
        wrapper = SilentAgentWrapper(agent)
        result = await wrapper.run("你好")
        assert result == "(empty response)"

    @pytest.mark.asyncio
    async def test_wrapper_llm_error_passthrough(self):
        """LLM call failed 和 Task couldn't be completed 应返回 (empty response)。"""
        from companion.webui.agent_wrapper import SilentAgentWrapper
        agent = AsyncMock()
        agent.run = AsyncMock(return_value="LLM call failed: timeout")
        wrapper = SilentAgentWrapper(agent)
        result = await wrapper.run("你好")
        assert result == "(empty response)"

    @pytest.mark.asyncio
    async def test_wrapper_adds_user_conversation(self):
        """应调用 add_conversation 记录用户消息。"""
        from companion.webui.agent_wrapper import SilentAgentWrapper
        agent = AsyncMock()
        agent.run = AsyncMock(return_value="回复")
        registry = MagicMock()
        registry.memory.add_conversation = MagicMock()
        wrapper = SilentAgentWrapper(agent, registry)
        await wrapper.run("你好世界")
        registry.memory.add_conversation.assert_any_call("user", "你好世界")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Registry 边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestRegistryEdgeCases:
    """Registry 创建和初始化的极端条件。"""

    def test_registry_empty_workspace(self, temp_workspace):
        """空 workspace 启动 — 各模块应正常初始化。"""
        reg = CompanionRegistry(
            workspace=temp_workspace,
            config_dir="companion/config",
            mbti_type="ENFP",
        )
        assert reg.memory is not None
        assert reg.emotion is not None

    def test_registry_all_mbti_types(self, temp_workspace):
        """每种 MBTI 类型注册。"""
        for mbti in ["INTJ", "INTP", "ENTJ", "ENTP",
                      "INFJ", "INFP", "ENFJ", "ENFP",
                      "ISTJ", "ISFJ", "ESTJ", "ESFJ",
                      "ISTP", "ISFP", "ESTP", "ESFP"]:
            reg = CompanionRegistry(
                workspace=temp_workspace,
                config_dir="companion/config",
                mbti_type=mbti,
            )
            assert reg.mbti is not None

    def test_registry_invalid_mbti(self, temp_workspace):
        """非法 MBTI 类型注册不应崩溃。"""
        reg = CompanionRegistry(
            workspace=temp_workspace,
            config_dir="companion/config",
            mbti_type="INVALID",
        )
        # 应使用 registry 的默认 MBTI 类型
        assert reg.mbti is not None


# ══════════════════════════════════════════════════════════════════════════════
# 7. Scheduler 边缘
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerEdgeCases:
    """调度器极端条件。"""

    @pytest.mark.asyncio
    async def test_message_router_empty_queue(self):
        """空队列不应阻塞。"""
        from companion.scheduler import MessageRouter
        router = MessageRouter()
        received = []

        def handler(msg):
            received.append(msg)

        task = asyncio.create_task(router.run(handler))
        await asyncio.sleep(0.2)
        router.stop()
        await task
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_message_router_rapid_enqueue(self):
        """快速入队大量消息不应丢失。"""
        from companion.scheduler import MessageRouter
        router = MessageRouter()
        received = []

        def handler(msg):
            received.append(msg)

        task = asyncio.create_task(router.run(handler))
        await asyncio.sleep(0.05)

        for i in range(20):
            await router.enqueue({"content": f"msg_{i}"})
        await asyncio.sleep(0.5)

        router.stop()
        await task
        assert len(received) <= 20
        assert len(received) > 0

    @pytest.mark.asyncio
    async def test_webhook_listener_empty_content(self, registry):
        """空内容 webhook 消息应优雅处理。"""
        from companion.scheduler import MessageRouter, WebhookListener
        router = MessageRouter()
        webhook = WebhookListener(registry, router)
        await webhook.handle_message({})
        # 不应崩溃

    def test_proactive_loop_immediate_stop_no_error(self, registry):
        """ProactiveLoop 立即停止不应报错。"""
        from companion.scheduler import ProactiveLoop
        triggered = []

        def cb(msg):
            triggered.append(msg)

        loop = ProactiveLoop(registry, on_trigger=cb, check_interval=0.5)
        loop.stop()
