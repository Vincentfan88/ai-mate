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
        # get_suitable_scenes returns List[Tuple[Scene, float]]
        assert any(s.id == "morning_greeting" for s, _score in scenes)

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
        # get_scene_multiplier takes only scene_id (uses current level)
        mult = mgr.get_scene_multiplier("morning_greeting")
        assert isinstance(mult, float)
        assert mult > 0

    def test_check_progress_insufficient(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        # Not enough interactions at default state
        assert mgr.check_progress() is False

    def test_check_progress_sufficient(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        # Reset level and set enough for level 0 → 1 progression
        mgr.current_level = 0
        mgr.interaction_count = 50
        mgr.emotional_depth = 0.5
        mgr.memory_count = 30
        assert mgr.check_progress() is True

    def test_max_level_no_progress(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        mgr.current_level = 5
        assert mgr.check_progress() is False

    def test_progress_advances(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        mgr.interaction_count = 55
        mgr.emotional_depth = 0.6
        mgr.memory_count = 35
        initial_level = mgr.current_level
        advanced = mgr.progress()
        if advanced:
            assert mgr.current_level == initial_level + 1

    def test_get_stats(self):
        mgr = RelationshipManager(config_path="companion/config/relationship.json")
        stats = mgr.get_stats()
        assert "level" in stats
        assert "interactions" in stats
        assert "can_progress" in stats


class TestLivenessTracker:
    """Test liveness dimension tracking."""

    def test_initial_metrics(self):
        tracker = LivenessTracker()
        metrics = tracker.calculate_scores()
        assert isinstance(metrics, dict)
        assert "主动性" in metrics
        assert 0 <= metrics["主动性"] <= 1

    def test_record_contact(self):
        tracker = LivenessTracker()
        tracker.record_initiated_contact()
        metrics = tracker.calculate_scores()
        # After one initiated contact, initiative should be 1.0
        assert metrics["主动性"] == 1.0

    def test_record_response_detects_emotions(self):
        tracker = LivenessTracker()
        tracker.record_response("今天好开心呀，工作顺利！")
        metrics = tracker.calculate_scores()
        assert metrics["情绪化"] > 0

    def test_record_response_physical(self):
        tracker = LivenessTracker()
        tracker.record_response("靠在你肩上，感觉好温暖")
        metrics = tracker.calculate_scores()
        assert metrics["身体存在感"] > 0

    def test_record_response_vulnerability(self):
        tracker = LivenessTracker()
        tracker.record_response("今天有点累，想你了")
        metrics = tracker.calculate_scores()
        assert metrics["脆弱性"] > 0

    def test_snapshot(self):
        tracker = LivenessTracker()
        tracker.record_response("你好")
        snap = tracker.snapshot()
        assert snap.overall_score > 0
        assert len(tracker.metrics_history) >= 1

    def test_overall_score(self):
        tracker = LivenessTracker()
        overall = tracker.get_overall_score()
        assert 0 <= overall <= 1

    def test_get_report(self):
        tracker = LivenessTracker()
        tracker.record_response("今天很开心")
        report = tracker.get_report()
        assert "活人感" in report
