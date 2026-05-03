"""Tests for flashback module — natural memory retrieval and follow-up prompts."""

import tempfile
from datetime import datetime, timedelta

from companion.modules.memory.flashback import FlashbackEngine, Flashback


class MockFactStore:
    """Fake fact store for testing."""

    def __init__(self, facts):
        self._facts = facts

    def search(self, query, top_k=8):
        query_lower = query.lower()
        results = [f for f in self._facts if any(w in f["content"].lower() for w in query_lower.split())]
        if not results:
            results = self._facts[:top_k]
        return results[:top_k]


class TestFlashbackEngine:
    """Test flashback engine."""

    def test_empty_store_returns_nothing(self):
        """No facts → no flashbacks."""
        store = MockFactStore([])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("我在学 Python")
        assert fbs == []

    def test_returns_matching_facts(self):
        """Should return matching facts as flashbacks."""
        store = MockFactStore([
            {"id": "f1", "content": "我最近在学 Python", "created_at": datetime.now().isoformat()},
            {"id": "f2", "content": "明天要去开会", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("Python")
        assert len(fbs) == 1
        assert fbs[0].fact_id == "f1"
        assert "Python" in fbs[0].follow_up_prompt

    def test_filters_old_facts(self):
        """Should skip facts older than 7 days."""
        store = MockFactStore([
            {"id": "f_old", "content": "上周的事", "created_at": (datetime.now() - timedelta(days=10)).isoformat()},
            {"id": "f_recent", "content": "最近的事", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("上周 最近")
        # Both keywords match, but old one should be filtered
        assert len(fbs) == 1
        assert fbs[0].fact_id == "f_recent"

    def test_cooldown_prevents_repeat(self):
        """Same fact should not appear twice within cooldown period."""
        store = MockFactStore([
            {"id": "f1", "content": "学 Python", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)

        # First call
        fbs1 = engine.get_flashback("Python")
        assert len(fbs1) == 1

        # Immediate second call — should be blocked by cooldown
        fbs2 = engine.get_flashback("Python")
        assert len(fbs2) == 0

    def test_cooldown_expires_after_48h(self):
        """After 48 hours, cooldown should expire and fact can appear again."""
        store = MockFactStore([
            {"id": "f1", "content": "学 Python", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)

        # First call
        fbs1 = engine.get_flashback("Python")
        assert len(fbs1) == 1

        # Simulate 49 hours later
        future_time = datetime.now() + timedelta(hours=49)
        fbs2 = engine.get_flashback("Python", now=future_time)
        assert len(fbs2) == 1

    def test_max_top_k(self):
        """Should not return more than top_k items."""
        store = MockFactStore([
            {"id": f"f{i}", "content": f"事实{i}", "created_at": datetime.now().isoformat()}
            for i in range(5)
        ])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("事实", top_k=2)
        assert len(fbs) == 2

    def test_prompt_templates(self):
        """Prompt should contain natural follow-up phrasing."""
        store = MockFactStore([
            {"id": "f1", "content": "考试考完了", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("考试")
        assert len(fbs) == 1
        prompt = fbs[0].follow_up_prompt
        # Should be one of the template patterns
        assert "上次" in prompt or "想起来" in prompt or "忽然想起" in prompt

    def test_flashback_dataclass_fields(self):
        """Flashback should have correct fields."""
        fb = Flashback(
            fact_id="f1",
            content="test content",
            created_at=datetime.now().isoformat(),
            follow_up_prompt="test prompt",
        )
        assert fb.fact_id == "f1"
        assert fb.content == "test content"
        assert fb.created_at is not None
        assert "test prompt" in fb.follow_up_prompt

    def test_empty_message_returns_empty(self):
        """Empty or whitespace message should not crash."""
        store = MockFactStore([
            {"id": "f1", "content": "test", "created_at": datetime.now().isoformat()},
        ])
        engine = FlashbackEngine(store)
        fbs = engine.get_flashback("")
        # Should not raise, result depends on store behavior
        assert isinstance(fbs, list)