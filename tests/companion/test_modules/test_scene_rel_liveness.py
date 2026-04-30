"""Tests for scene, relationship, and liveness modules."""

from companion.modules.scene import SceneLibrary
from companion.modules.relationship import RelationshipManager
from companion.modules.liveness import LivenessTracker, LivenessMetrics


class TestSceneLibrary:
    """Test scene library."""

    def test_load_scenes(self):
        library = SceneLibrary(config_path="companion/config/scenes.json")
        assert len(library.scenes) >= 10

    def test_get_scene(self):
        library = SceneLibrary(config_path="companion/config/scenes.json")
        scene = library.get_scene("morning_greeting")
        assert scene is not None
        assert scene.name == "早安问候"

    def test_suitable_scenes(self):
        library = SceneLibrary(config_path="companion/config/scenes.json")
        scenes = library.get_suitable_scenes(hour=8, mood="idle")
        assert len(scenes) > 0
        assert any(s.id == "morning_greeting" for s in scenes)

    def test_scene_hour_check(self):
        library = SceneLibrary(config_path="companion/config/scenes.json")
        scene = library.get_scene("morning_greeting")
        assert scene.is_suitable_for_hour(7)
        assert not scene.is_suitable_for_hour(22)


class TestRelationshipManager:
    """Test relationship stage management."""

    def test_load_stages(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        assert len(mgr.stages) == 6

    def test_get_stage(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        stage = mgr.get_stage(0)
        assert stage.name == "stranger"
        assert stage.name_cn == "陌生人"

    def test_scene_multiplier(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        mult = mgr.get_scene_multiplier(0, "morning_greeting")
        assert mult == 1.5  # Stranger stage multiplier

    def test_can_progress(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        # Not enough interactions
        assert mgr.can_progress(0, interactions=5, emotional_depth=0.1, memory_count=5) is False
        # Enough for acquaintance (needs 50 interactions, 0.5 depth, 30 memories)
        assert mgr.can_progress(0, interactions=55, emotional_depth=0.6, memory_count=35) is True

    def test_max_level_no_progress(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        assert mgr.can_progress(5, interactions=9999, emotional_depth=1.0, memory_count=9999) is False


class TestLivenessTracker:
    """Test liveness dimension tracking."""

    def test_initial_metrics(self):
        tracker = LivenessTracker()
        metrics = tracker.get_metrics()
        assert 0 <= metrics.主动性 <= 1
        assert 0 <= metrics.overall_score() <= 1

    def test_update_metrics(self):
        tracker = LivenessTracker()
        tracker.update(主动性=0.8, 情绪化=0.9)
        metrics = tracker.get_metrics()
        assert metrics.主动性 == 0.8
        assert metrics.情绪化 == 0.9

    def test_snapshot(self):
        tracker = LivenessTracker()
        tracker.update(主动性=0.7)
        tracker.snapshot()
        assert len(tracker.history) == 1
        assert tracker.history[0].主动性 == 0.7

    def test_overall_score(self):
        tracker = LivenessTracker()
        tracker.update(
            主动性=1.0, 一致性=1.0, 成长性=1.0, 情绪化=1.0,
            脆弱性=1.0, 身体存在感=1.0, 不可预测性=1.0, 依恋度=1.0,
        )
        assert tracker.get_overall() == 1.0
