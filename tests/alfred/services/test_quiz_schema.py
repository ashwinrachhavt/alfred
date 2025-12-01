import pytest
from alfred.services.agents.quiz import Quiz, validate_quiz


def test_quiz_schema_valid():
    data = {"topic": "LangGraph", "questions": ["What is a node?", "Define state."]}
    q = validate_quiz(data)
    assert isinstance(q, Quiz)
    assert q.topic == "LangGraph"
    assert len(q.questions) == 2


def test_quiz_schema_invalid_raises():
    bad = {"topic": "", "questions": []}
    with pytest.raises(Exception):
        validate_quiz(bad)
