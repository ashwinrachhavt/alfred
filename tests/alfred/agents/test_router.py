"""Tests for the hybrid intent router."""
from alfred.agents.router import heuristic_classify, IntentMatch


def test_import_intent():
    match = heuristic_classify("import my notion pages")
    assert match is not None
    assert match.intent == "import"
    assert match.team == "ingest_team"


def test_search_intent():
    match = heuristic_classify("what do I know about epistemology")
    assert match is not None
    assert match.intent == "search_kb"
    assert match.team == "knowledge_team"


def test_research_intent():
    match = heuristic_classify("research transformer architectures on arxiv")
    assert match is not None
    assert match.intent == "research"
    assert match.team == "synthesis_team"


def test_write_intent():
    match = heuristic_classify("write a summary of my notes on stoicism")
    assert match is not None
    assert match.intent == "write"
    assert match.team == "synthesis_team"


def test_learn_intent():
    match = heuristic_classify("show me cards due for review")
    assert match is not None
    assert match.intent == "learn"
    assert match.team == "knowledge_team"


def test_ambiguous_returns_none():
    match = heuristic_classify("tell me something interesting")
    assert match is None
