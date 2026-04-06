"""Tests for the hybrid intent router."""
from alfred.agents.router import IntentMatch, _classify_action, _is_conversational


def test_import_intent():
    match = _classify_action("import my notion pages")
    assert match is not None
    assert match.intent == "import"
    assert match.destination == "ingest_team"


def test_search_intent():
    match = _classify_action("what do i know about epistemology")
    assert match is not None
    assert match.intent == "search_kb"
    assert match.destination == "knowledge_team"


def test_research_intent():
    match = _classify_action("research transformer architectures on arxiv")
    assert match is not None
    assert match.intent == "research"
    assert match.destination == "synthesis_team"


def test_write_intent():
    match = _classify_action("write a summary of my notes on stoicism")
    assert match is not None
    assert match.intent == "write"
    assert match.destination == "synthesis_team"


def test_learn_intent():
    match = _classify_action("review my cards due for review")
    assert match is not None
    assert match.intent == "learn"
    assert match.destination == "knowledge_team"


def test_ambiguous_returns_none():
    match = _classify_action("tell me something interesting")
    assert match is None


def test_conversational_greeting():
    assert _is_conversational("hello there") is True


def test_conversational_question():
    assert _is_conversational("what is epistemology?") is True


def test_action_not_conversational():
    # Action patterns should be classified by _classify_action, not _is_conversational
    match = _classify_action("import my notion pages")
    assert match is not None
