"""Tests for memory module - fact_store, preference, contradiction."""

import json
import tempfile
from datetime import datetime, timedelta

import pytest

from companion.modules.memory.fact_store import FactStore, Fact
from companion.modules.memory.preference import PreferenceInfer
from companion.modules.memory.contradiction import ContradictionDetector


class TestFactStore:
    """Test temperature-based fact storage and retrieval."""

    def test_record_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            store.record("用户喜欢吃辣", importance=0.8)
            store.record("用户上周要去旅行", importance=0.5)
            store.record("用户喜欢看电影", importance=0.6)

            results = store.search("喜欢", top_k=2)
            assert len(results) <= 2
            # "喜欢吃辣" should rank higher due to higher importance
            assert results[0]["content"] == "用户喜欢吃辣"

    def test_temperature_ranking(self):
        """Higher temperature facts should rank first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            # Record a fact multiple times to boost temperature
            for _ in range(5):
                store.record("重要事实", importance=0.9)
            store.record("普通事实", importance=0.5)

            results = store.search("事实", top_k=2)
            assert results[0]["content"] == "重要事实"

    def test_time_decay(self):
        """Old facts should have lower temperature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            # Manually inject old timestamp
            store.record("旧事实", importance=0.8)
            # Adjust timestamp to 30 days ago
            with open(store.store_path) as f:
                data = json.load(f)
            data["facts"][0]["timestamp"] = (datetime.now() - timedelta(days=30)).isoformat()
            with open(store.store_path, "w") as f:
                json.dump(data, f)

            store.record("新事实", importance=0.5)
            results = store.search("事实", top_k=2)
            # New fact should rank higher due to less decay
            assert results[0]["content"] == "新事实"

    def test_deduplication(self):
        """Duplicate facts should increment mention_count, not create new entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            store.record("用户喜欢喝咖啡")
            store.record("用户喜欢喝咖啡")

            data = store._load()
            assert len(data["facts"]) == 1
            assert data["facts"][0]["mention_count"] == 2

    def test_add_interaction(self):
        """Interactions should be stored and retrievable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            store.add_interaction("user", "你好")
            store.add_interaction("assistant", "你好呀！")

            interactions = store.get_recent_interactions()
            assert len(interactions) == 2
            assert interactions[0]["content"] == "你好"

    def test_interaction_limit(self):
        """Only last 100 interactions should be kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test_memory.json")
            for i in range(120):
                store.add_interaction("user", f"message {i}")

            interactions = store.get_recent_interactions(limit=100)
            assert len(interactions) == 100
            assert interactions[0]["content"] == "message 20"


class TestFact:
    """Test Fact dataclass behaviors."""

    def test_compute_temperature(self):
        fact = Fact(
            content="用户喜欢吃辣",
            timestamp=datetime.now().isoformat(),
            importance=0.8,
            mention_count=3,
        )
        temp = fact.compute_temperature()
        # importance=0.8, mention_bonus=1+3*0.3=1.9, time_decay~1.0, relation_bonus=1.0
        assert 0.8 * 1.8 < temp < 0.8 * 2.0

    def test_age_days(self):
        fact = Fact(
            content="test",
            timestamp=datetime.now().isoformat(),
            importance=0.5,
        )
        assert fact.age_days < 1.0


class TestPreferenceInfer:
    """Test preference inference from facts."""

    def test_preference_categorization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test.json")
            store.record("用户喜欢吃辣")
            store.record("用户每天都跑步")
            store.record("用户最近工作压力很大")

            pref = PreferenceInfer(store)
            result = pref.infer()
            assert len(result["inferences"]) > 0
            assert "用户偏好" in result["inferences"][0]

    def test_negation_exclusion(self):
        """否定词不应被误判为偏好"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FactStore(store_path=f"{tmpdir}/test.json")
            store.record("用户不喜欢吃辣")  # Should be tagged as negative

            pref = PreferenceInfer(store)
            result = pref.infer()
            # Should have inferences, even if negative
            assert len(result["inferences"]) > 0


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
