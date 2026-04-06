"""Tests for VocabularyEntry model."""

from __future__ import annotations


class TestVocabularyEntryModel:
    """Verify VocabularyEntry field defaults and constraints."""

    def test_import(self):
        from alfred.models.vocabulary import SaveIntent, VocabularyEntry

        assert VocabularyEntry is not None
        assert SaveIntent is not None

    def test_default_fields(self):
        from alfred.models.vocabulary import SaveIntent, VocabularyEntry

        entry = VocabularyEntry(word="ephemeral", save_intent=SaveIntent.learning)
        assert entry.word == "ephemeral"
        assert entry.save_intent == SaveIntent.learning
        assert entry.language == "en"
        assert entry.bloom_level == 1
        assert entry.definitions is None
        assert entry.etymology is None
        assert entry.pronunciation_ipa is None
        assert entry.zettel_id is None
        assert entry.domain_tags is None

    def test_save_intent_enum_values(self):
        from alfred.models.vocabulary import SaveIntent

        assert SaveIntent.learning.value == "learning"
        assert SaveIntent.reference.value == "reference"
        assert SaveIntent.encountered.value == "encountered"
