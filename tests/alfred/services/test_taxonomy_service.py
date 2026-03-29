"""Tests for taxonomy service and slug normalization."""

from __future__ import annotations

from alfred.schemas.taxonomy import to_display_name, to_slug


class TestSlugNormalization:
    """Test slug normalization utility."""

    def test_to_slug_spaces(self):
        assert to_slug("Machine Learning") == "machine-learning"

    def test_to_slug_underscores(self):
        assert to_slug("machine_learning") == "machine-learning"

    def test_to_slug_special_chars(self):
        assert to_slug("AI/ML & Data") == "ai-ml-data"

    def test_to_slug_uppercase_domain(self):
        assert to_slug("AI") == "ai"

    def test_to_slug_uppercase_with_underscores(self):
        assert to_slug("SYSTEM_DESIGN") == "system-design"

    def test_to_slug_movies_pop_culture(self):
        assert to_slug("MOVIES_POP_CULTURE") == "movies-pop-culture"

    def test_to_slug_caps_at_128_chars(self):
        long_input = "a" * 200
        result = to_slug(long_input)
        assert len(result) == 128
        assert result == "a" * 128

    def test_to_slug_collapses_multiple_hyphens(self):
        assert to_slug("multi---hyphen--test") == "multi-hyphen-test"

    def test_to_slug_strips_leading_trailing_hyphens(self):
        assert to_slug("--leading-trailing--") == "leading-trailing"

    def test_to_slug_mixed_case(self):
        assert to_slug("CamelCaseExample") == "camelcaseexample"


class TestDisplayName:
    """Test display name conversion."""

    def test_to_display_name_basic(self):
        assert to_display_name("machine-learning") == "Machine Learning"

    def test_to_display_name_single_word(self):
        assert to_display_name("ai") == "Ai"

    def test_to_display_name_multiple_words(self):
        assert to_display_name("system-design-patterns") == "System Design Patterns"
