"""Tests for MBTI module."""

from companion.modules.mbti import MBTIAdapter, get_type, ALL_TYPES


class TestMBTITypes:
    """Test MBTI type definitions."""

    def test_all_16_types_exist(self):
        assert len(ALL_TYPES) == 16

    def test_get_type_valid(self):
        for code in ["ENFP", "INTJ", "ESFJ", "ISTP"]:
            mbti = get_type(code)
            assert mbti is not None
            assert mbti.code == code

    def test_get_type_invalid(self):
        assert get_type("XXXX") is None

    def test_type_has_all_fields(self):
        mbti = get_type("ENFP")
        assert mbti.code == "ENFP"
        assert mbti.name
        assert mbti.nickname
        assert len(mbti.strengths) > 0
        assert len(mbti.weaknesses) > 0
        assert mbti.communication_style
        assert mbti.emotional_expression
        assert len(mbti.relationship_patterns) > 0
        assert len(mbti.vulnerability_triggers) > 0


class TestMBTIAdapter:
    """Test MBTI adapter profile generation."""

    def test_get_profile_extravert(self):
        adapter = MBTIAdapter()
        profile = adapter.get_profile("ENFP")
        assert profile.type.code == "ENFP"
        assert profile.speech.max_length > 0
        assert len(profile.speech.typical_particles) > 0

    def test_get_profile_introvert(self):
        adapter = MBTIAdapter()
        profile = adapter.get_profile("INTJ")
        assert profile.type.code == "INTJ"
        assert profile.behavior.情感外放度 <= 0.5

    def test_extravert_vs_introvert_speech(self):
        adapter = MBTIAdapter()
        extravert = adapter.get_profile("ENFP")
        introvert = adapter.get_profile("INTJ")
        # Extraverts should have more emojis
        assert len(extravert.speech.typical_emojis) >= len(introvert.speech.typical_emojis)

    def test_thinking_vs_feeling_emotional(self):
        adapter = MBTIAdapter()
        thinker = adapter.get_profile("INTJ")
        feeler = adapter.get_profile("ENFP")
        # Feelers should have higher self-disclosure
        assert feeler.emotional.self_disclosure_tendency >= thinker.emotional.self_disclosure_tendency

    def test_scene_weights_differ_by_type(self):
        adapter = MBTIAdapter()
        extravert = adapter.get_profile("ENFP")
        introvert = adapter.get_profile("INTJ")
        # Different scene weight multipliers
        ext_keys = set(extravert.scene_weights.multipliers.keys())
        int_keys = set(introvert.scene_weights.multipliers.keys())
        assert ext_keys != int_keys or extravert.scene_weights.multipliers != introvert.scene_weights.multipliers

    def test_get_all_types(self):
        adapter = MBTIAdapter()
        types = adapter.get_all_types()
        assert len(types) == 16
        assert "ENFP" in types
        assert "INTJ" in types

    def test_invalid_type_raises(self):
        adapter = MBTIAdapter()
        try:
            adapter.get_profile("XXXX")
            assert False, "Should raise ValueError"
        except ValueError:
            pass
