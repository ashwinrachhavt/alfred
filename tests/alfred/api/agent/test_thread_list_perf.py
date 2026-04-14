"""Performance test for agent thread listing endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from alfred.main import app

client = TestClient(app)


@pytest.mark.integration
def test_list_threads_returns_200():
    """Verify thread listing endpoint works after refactor."""
    response = client.get("/api/agent/threads?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for thread in data:
        assert "message_count" in thread
        assert isinstance(thread["message_count"], int)
