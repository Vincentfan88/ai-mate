"""Tests for time awareness module — extraction, persistence, and follow-up."""

import tempfile
from datetime import datetime, timedelta

from companion.modules.extras.time_awareness import TimeAwareness, TimeEvent


class TestTimeAwareness:
    """Test TimeAwareness extraction, storage, and checking."""

    def test_initial_state_empty(self):
        """New instance should have no events."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            assert ta.get_pending() == []

    def test_extract_relative_keywords(self):
        """Should extract time events from relative keywords."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            event = ta.extract_from_message("明天我去面试", now=now)
            assert event is not None
            assert event.original_text == "明天"
            assert event.status == "pending"

            pending = ta.get_pending()
            assert len(pending) == 1

    def test_extract_n_days(self):
        """Should extract 'N天后' patterns."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            event = ta.extract_from_message("3天后有考试", now=now)
            assert event is not None
            assert event.original_text == "3天后"

    def test_extract_n_weeks(self):
        """Should extract 'N周后' patterns."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            event = ta.extract_from_message("2周后出差", now=now)
            assert event is not None
            assert event.original_text == "2周后"

    def test_extract_specific_date(self):
        """Should extract 'MM月DD日' patterns."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime(2026, 5, 3)

            event = ta.extract_from_message("6月15号考试", now=now)
            assert event is not None
            assert "6月15日" in event.original_text

    def test_no_match_returns_none(self):
        """Messages without time references should return None."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            event = ta.extract_from_message("今天心情很好", now=now)
            # "今天" should still match
            assert event is not None

            event = ta.extract_from_message("hello world", now=now)
            assert event is None

    def test_multiple_events_accumulate(self):
        """Multiple extractions should accumulate."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            ta.extract_from_message("明天去开会", now=now)
            ta.extract_from_message("后天出差", now=now)

            pending = ta.get_pending()
            assert len(pending) == 2

    def test_check_pending_marks_missed(self):
        """check_pending should return due events and mark them as missed."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            # Create an event in the past
            ev = TimeEvent(
                id="test_past",
                content="过去的考试",
                original_text="明天",
                target_time=now - timedelta(hours=2),
                status="pending",
            )
            ta._events.append(ev)

            due = ta.check_pending(now=now)
            assert len(due) == 1
            assert due[0].status == "missed"

    def test_check_pending_does_not_mark_future(self):
        """Future pending events should not be marked as missed."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            ev = TimeEvent(
                id="test_future",
                content="未来的面试",
                original_text="下周",
                target_time=now + timedelta(days=3),
                status="pending",
            )
            ta._events.append(ev)

            due = ta.check_pending(now=now)
            assert len(due) == 0
            assert ta.get_pending()[0].status == "pending"

    def test_mark_done(self):
        """Should mark event as done."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")

            ev = ta.extract_from_message("明天去面试")
            assert ev.status == "pending"

            result = ta.mark_done(ev.id)
            assert result is True

            assert ta._events[0].status == "done"

    def test_mark_done_nonexistent(self):
        """Should return False for non-existent event."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            assert ta.mark_done("nonexistent") is False

    def test_persistence(self):
        """Events should survive reload."""
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/time_events.json"
            now = datetime.now()

            ta1 = TimeAwareness(state_path=path)
            ta1.extract_from_message("明天去面试", now=now)

            ta2 = TimeAwareness(state_path=path)
            pending = ta2.get_pending()
            assert len(pending) == 1
            assert pending[0].content == "明天去面试"

    def test_get_context_text(self):
        """Should return readable context text."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            now = datetime.now()

            ta.extract_from_message("明天去面试", now=now)
            ctx = ta.get_context_text(now=now)
            assert "时间提醒" in ctx
            assert "明天" in ctx

    def test_get_context_text_empty_when_no_events(self):
        """Should return empty string when no events."""
        with tempfile.TemporaryDirectory() as td:
            ta = TimeAwareness(state_path=f"{td}/time_events.json")
            assert ta.get_context_text() == ""

    def test_event_serialization_roundtrip(self):
        """TimeEvent should serialize and deserialize correctly."""
        now = datetime.now()
        ev = TimeEvent(
            id="test_1",
            content="test content",
            original_text="明天",
            target_time=now + timedelta(days=1),
            status="pending",
        )
        d = ev.to_dict()
        ev2 = TimeEvent.from_dict(d)
        assert ev2.id == ev.id
        assert ev2.content == ev.content
        assert ev2.status == ev.status
