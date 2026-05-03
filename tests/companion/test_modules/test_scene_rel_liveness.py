"""Tests for scene and liveness modules."""

from companion.modules.scene import SceneLibrary
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
        assert any(s.id == "morning_greeting" for s, _score in scenes)

    def test_scene_hour_check(self):
        library = SceneLibrary(config_path="companion/config/scenes.json")
        scene = library.get_scene("morning_greeting")
        assert scene.is_suitable_for_hour(7)
        assert not scene.is_suitable_for_hour(22)


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
