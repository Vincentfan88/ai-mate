"""Tests for memory module — JsonFactStore, MdConversationLog, InteractionCache, PreferenceInfer."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from companion.modules.memory.json_store import JsonFactStore
from companion.modules.memory.md_log import MdConversationLog
from companion.modules.memory.interaction_cache import InteractionCache
from companion.modules.memory.preference import PreferenceInfer
from companion.modules.memory.contradiction import ContradictionDetector


class TestJsonFactStore:
    """Test JSON fact storage with temperature ranking."""

    def test_record_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            store.record("用户喜欢吃辣", importance=0.8)
            store.record("用户上周要去旅行", importance=0.5)
            store.record("用户喜欢看电影", importance=0.6)

            results = store.search("喜欢", top_k=2)
            assert len(results) <= 2
            assert results[0]["content"] == "用户喜欢吃辣"

    def test_temperature_ranking(self):
        """Higher temperature facts should rank first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            for _ in range(5):
                store.record("重要事实", importance=0.9)
            store.record("普通事实", importance=0.5)

            results = store.search("事实", top_k=2)
            assert results[0]["content"] == "重要事实"

    def test_time_decay(self):
        """Old facts should have lower temperature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            store.record("旧事实", importance=0.8)
            # Inject old timestamp
            with open(store.facts_path) as f:
                data = json.load(f)
            data[0]["timestamp"] = (datetime.now() - timedelta(days=30)).isoformat()
            with open(store.facts_path, "w") as f:
                json.dump(data, f)
            store._facts = data

            store.record("新事实", importance=0.5)
            results = store.search("事实", top_k=2)
            assert results[0]["content"] == "新事实"

    def test_deduplication(self):
        """Duplicate facts should increment mention_count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            store.record("用户喜欢喝咖啡")
            store.record("用户喜欢喝咖啡")

            assert len(store._facts) == 1
            assert store._facts[0]["mention_count"] == 2

    def test_persona_gate(self):
        """AI persona facts should not be stored as user facts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            store.record("我是AI助手", source="ai_attribute")

            user_facts = [f for f in store._facts if f.get("source") != "ai_attribute"]
            assert len(user_facts) == 0

    def test_compact(self):
        """Low-temperature facts should be cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonFactStore(facts_path=f"{tmpdir}/facts.json")
            store.record("新鲜事实", importance=0.8)
            store.record("旧事实", importance=0.1)
            # Make old fact very old
            with open(store.facts_path) as f:
                data = json.load(f)
            data[1]["timestamp"] = (datetime.now() - timedelta(days=90)).isoformat()
            store._facts = data

            removed = store.compact()
            assert removed >= 1
            assert len(store._facts) == 1


class TestMdConversationLog:
    """Test markdown conversation logging."""

    def test_append_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = MdConversationLog(log_dir=tmpdir)
            log.append("user", "你好呀", "2026-05-01T21:30:00")
            log.append("assistant", "你好！在呢~", "2026-05-01T21:30:05")

            recent = log.get_recent(limit=2)
            assert len(recent) == 2
            assert recent[0]["role"] == "user"
            assert recent[0]["content"] == "你好呀"

    def test_new_file_has_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = MdConversationLog(log_dir=tmpdir)
            log.append("user", "第一条消息", "2026-06-15T10:00:00")

            file_path = Path(tmpdir) / "2026-06-15.md"
            content = file_path.read_text(encoding="utf-8")
            assert content.startswith("# 2026-06-15")

    def test_append_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = MdConversationLog(log_dir=tmpdir)
            log.append_note("用户喜欢吃辣", "2026-05-01T21:30:00")

            file_path = Path(tmpdir) / "2026-05-01.md"
            content = file_path.read_text(encoding="utf-8")
            assert "[记录]" in content


class TestInteractionCache:
    """Test rolling interaction cache."""

    def test_add_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = InteractionCache(cache_path=f"{tmpdir}/cache.json")
            cache.add("user", "你好")
            cache.add("assistant", "你好呀！")

            recent = cache.get_recent(limit=2)
            assert len(recent) == 2
            assert recent[0]["content"] == "你好"

    def test_rolling_truncation(self):
        """Only last 20 interactions should be kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = InteractionCache(cache_path=f"{tmpdir}/cache.json")
            for i in range(30):
                cache.add("user", f"message {i}")

            all_items = cache.get_all()
            assert len(all_items) == 20
            assert all_items[0]["content"] == "message 10"


class TestContradictionDetector:
    """Test contradiction detection."""

    def test_detect_contradiction(self):
        detector = ContradictionDetector()
        facts = [
            {"content": "用户喜欢吃辣"},
            {"content": "用户讨厌吃辣"},
        ]
        result = detector.detect(facts)
        assert len(result) == 1
        assert result[0]["conflict_keywords"] == ("喜欢", "讨厌")

    def test_no_contradiction(self):
        detector = ContradictionDetector()
        facts = [
            {"content": "用户喜欢吃辣"},
            {"content": "用户喜欢看电影"},
        ]
        result = detector.detect(facts)
        assert len(result) == 0

    def test_should_follow_up(self):
        detector = ContradictionDetector()
        assert detector.should_follow_up([]) is False
        assert detector.should_follow_up([{"fact1": {}, "fact2": {}}]) is True


class TestMemorySystem:
    """Test MemorySystem integration."""

    def test_full_flow(self):
        from companion.modules.memory import MemorySystem

        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemorySystem(
                workspace=tmpdir,
                persona_path=None,
            )

            # Record facts
            memory.record("用户喜欢吃辣", importance=0.7)
            memory.record("用户工作很忙", importance=0.5)

            # Search
            results = memory.search("喜欢")
            assert len(results) > 0
            assert results[0]["content"] == "用户喜欢吃辣"

            # Add conversation
            memory.add_conversation("user", "今天好累")
            memory.add_conversation("assistant", "辛苦啦~")

            recent = memory.get_recent_conversations()
            assert len(recent) == 2

    def test_persona_loading(self):
        from companion.modules.memory import MemorySystem

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a persona file
            persona_path = f"{tmpdir}/persona.json"
            with open(persona_path, "w", encoding="utf-8") as f:
                json.dump({
                    "name": "小美",
                    "description": "用户的女朋友",
                    "personality": {
                        "core_traits": ["温柔", "体贴", "有个性"],
                    },
                    "speaking_style": {
                        "particles": ["呀", "嘛", "呢"],
                    },
                }, f)

            memory = MemorySystem(
                workspace=tmpdir,
                persona_path=persona_path,
            )

            summary = memory.get_persona_summary()
            assert "小美" in summary
            assert "女朋友" in summary
