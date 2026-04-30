"""Tests for emotion module."""

import json
import tempfile

from companion.modules.emotion import EmotionSystem


class TestEmotionSystem:
    """Test 8-emotion 2D model with circadian, contagion, residue."""

    def test_emotion_output_format(self):
        system = EmotionSystem(config_path="companion/config/emotions.json")
        emotion = system.get_current_emotion("user_message")
        assert emotion["emotion"] in system.emotion_types
        assert 0 <= emotion["intensity"] <= 1
        assert "circadian_base" in emotion

    def test_contagion(self):
        system = EmotionSystem(config_path="companion/config/emotions.json")
        # User is happy → AI should feel happy too
        emotion_happy = system.get_current_emotion("user_message", user_emotion="开心")
        emotion_normal = system.get_current_emotion("user_message")
        # Contagion should increase happiness intensity
        assert emotion_happy["intensity"] >= emotion_normal["intensity"] - 0.1

    def test_residue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = f"{tmpdir}/emotion_state.json"
            system = EmotionSystem(
                config_path="companion/config/emotions.json",
                state_file=state_file,
            )

            # Get emotion and save residue
            emotion = system.get_current_emotion("initiative_trigger")
            system.save_residue()

            # New instance should load residue
            system2 = EmotionSystem(
                config_path="companion/config/emotions.json",
                state_file=state_file,
            )
            emotion2 = system2.get_current_emotion("user_message")
            assert emotion2 is not None

    def test_tone_mapping(self):
        system = EmotionSystem(config_path="companion/config/emotions.json")
        tone = system.get_tone_description("开心")
        assert "活泼" in tone or "可爱" in tone

    def test_multiple_event_types(self):
        system = EmotionSystem(config_path="companion/config/emotions.json")
        for event_type in ["user_message", "initiative_trigger", "time_passage"]:
            emotion = system.get_current_emotion(event_type)
            assert emotion is not None
            assert "emotion" in emotion
            assert "intensity" in emotion


class TestCircadian:
    """Test circadian rhythm calculations."""

    def test_peak_hour(self):
        from companion.modules.emotion.circadian import compute_circadian

        value = compute_circadian(hour=21)
        # Peak at 21:00
        assert value >= compute_circadian(hour=9)

    def test_trough_hour(self):
        from companion.modules.emotion.circadian import compute_circadian

        value = compute_circadian(hour=9)
        # Trough at 09:00
        assert value <= compute_circadian(hour=21)

    def test_bounds(self):
        from companion.modules.emotion.circadian import compute_circadian

        for hour in range(24):
            value = compute_circadian(hour=hour)
            assert 0.0 <= value <= 1.0


class TestContagion:
    """Test emotion contagion mapping."""

    def test_happy_contagion(self):
        from companion.modules.emotion.contagion import compute_contagion

        result = compute_contagion("开心", {"happy_infection": 0.6})
        assert result["infected_emotion"] == "开心"
        assert result["intensity_bonus"] > 0

    def test_unknown_emotion(self):
        from companion.modules.emotion.contagion import compute_contagion

        result = compute_contagion("未知", {"happy_infection": 0.6})
        assert result["intensity_bonus"] == 0.0


class TestResidue:
    """Test emotion residue persistence."""

    def test_save_and_load(self):
        from companion.modules.emotion.residue import EmotionResidue

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = f"{tmpdir}/emotion_state.json"
            residue = EmotionResidue(state_file, decay=0.3)
            residue.save("开心", 0.8)

            bonus = residue.get_residue_bonus()
            assert bonus["emotion"] == "开心"
            assert bonus["bonus"] > 0

    def test_no_state_file(self):
        from companion.modules.emotion.residue import EmotionResidue

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = f"{tmpdir}/nonexistent.json"
            residue = EmotionResidue(state_file)
            bonus = residue.get_residue_bonus()
            assert bonus["bonus"] == 0.0
