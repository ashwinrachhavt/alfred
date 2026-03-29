"""Tests for taxonomy canonicalization service."""

import pytest
from alfred.services.taxonomy_canonicalizer import find_canonical_match


def test_exact_match():
    """Test exact match returns the canonical slug."""
    existing = ["ai-engineering", "finance", "philosophy"]
    result = find_canonical_match("ai-engineering", existing)
    assert result == "ai-engineering"


def test_fuzzy_match_hyphen_variants():
    """Test underscore to hyphen normalization."""
    existing = ["ai-engineering", "finance"]
    result = find_canonical_match("ai_engineering", existing)
    assert result == "ai-engineering"


def test_fuzzy_match_synonyms():
    """Test synonym map returns canonical term."""
    existing = ["ai-engineering", "finance", "philosophy"]

    # Test various AI synonyms
    assert find_canonical_match("artificial-intelligence", existing) == "ai-engineering"
    assert find_canonical_match("ai", existing) == "ai-engineering"
    assert find_canonical_match("machine-learning", existing) == "ai-engineering"
    assert find_canonical_match("ml", existing) == "ai-engineering"
    assert find_canonical_match("deep-learning", existing) == "ai-engineering"

    # Test system design synonyms
    existing_with_sd = existing + ["system-design"]
    assert find_canonical_match("distributed-systems", existing_with_sd) == "system-design"
    assert find_canonical_match("microservices", existing_with_sd) == "system-design"

    # Test finance synonyms
    assert find_canonical_match("investing", existing) == "finance"
    assert find_canonical_match("investments", existing) == "finance"
    assert find_canonical_match("stocks", existing) == "finance"
    assert find_canonical_match("crypto", existing) == "finance"

    # Test philosophy synonyms
    assert find_canonical_match("stoicism", existing) == "philosophy"
    assert find_canonical_match("ethics", existing) == "philosophy"
    assert find_canonical_match("existentialism", existing) == "philosophy"

    # Test politics synonyms
    existing_with_politics = existing + ["politics"]
    assert find_canonical_match("geopolitics", existing_with_politics) == "politics"
    assert find_canonical_match("international-relations", existing_with_politics) == "politics"


def test_no_match_returns_none():
    """Test that unmatched terms return None."""
    existing = ["ai-engineering", "finance", "philosophy"]
    result = find_canonical_match("cooking-recipes", existing)
    assert result is None


def test_plural_normalization():
    """Test plural to singular normalization."""
    existing = ["investment", "startup"]

    # Plural should match singular
    assert find_canonical_match("investments", existing) == "investment"
    assert find_canonical_match("startups", existing) == "startup"


def test_case_insensitive():
    """Test case-insensitive matching."""
    existing = ["ai-engineering", "finance"]
    assert find_canonical_match("AI-Engineering", existing) == "ai-engineering"
    assert find_canonical_match("FINANCE", existing) == "finance"


def test_fuzzy_similarity_threshold():
    """Test fuzzy matching with high similarity."""
    existing = ["ai-engineering"]

    # High similarity should match
    assert find_canonical_match("ai-engineer", existing) == "ai-engineering"
    assert find_canonical_match("aiengineering", existing) == "ai-engineering"

    # Low similarity should not match
    assert find_canonical_match("biology", existing) is None
    assert find_canonical_match("cooking", existing) is None


def test_empty_existing_list():
    """Test behavior with empty existing list."""
    result = find_canonical_match("ai-engineering", [])
    assert result is None


def test_priority_order():
    """Test that exact match takes priority over synonyms."""
    existing = ["artificial-intelligence", "ai-engineering"]

    # Even though "artificial-intelligence" is a synonym for "ai-engineering",
    # if it exists as its own node, exact match should win
    result = find_canonical_match("artificial-intelligence", existing)
    assert result == "artificial-intelligence"
