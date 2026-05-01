from __future__ import annotations

from alfred.schemas.whiteboard import WhiteboardCreate, WhiteboardRevisionCreate


def test_whiteboard_schemas_accept_large_applied_prompt() -> None:
    large_prompt = "Expand this canvas with detailed system context.\n" * 1500

    create_payload = WhiteboardCreate(
        title="Large prompt board",
        applied_prompt=large_prompt,
    )
    revision_payload = WhiteboardRevisionCreate(
        scene_json={"elements": []},
        applied_prompt=large_prompt,
    )

    assert create_payload.applied_prompt == large_prompt
    assert revision_payload.applied_prompt == large_prompt
