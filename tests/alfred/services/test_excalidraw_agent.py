"""Tests for Excalidraw AI agent service."""

from __future__ import annotations

import json

from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response


class TestBuildDiagramPrompt:
    """Test diagram prompt building."""

    def test_prompt_includes_user_request(self):
        """Prompt should contain the user's diagram request."""
        user_request = "draw a flowchart for user authentication"
        prompt = build_diagram_prompt(user_request)

        assert user_request in prompt
        assert "flowchart" in prompt.lower()
        assert "authentication" in prompt.lower()

    def test_prompt_includes_element_schema(self):
        """Prompt should explain the structured diagram format."""
        prompt = build_diagram_prompt("draw a simple diagram")

        assert '"diagram_type"' in prompt
        assert '"layout"' in prompt
        assert '"nodes"' in prompt
        assert '"edges"' in prompt
        assert "flowchart" in prompt.lower()
        assert "mindmap" in prompt.lower()

    def test_prompt_includes_canvas_context(self):
        """Prompt should include canvas context when provided."""
        user_request = "add more boxes"
        canvas_context = "Existing elements: [box labeled 'Start']"
        prompt = build_diagram_prompt(user_request, canvas_context)

        assert canvas_context in prompt
        assert user_request in prompt


class TestParseDiagramResponse:
    """Test parsing LLM responses into Excalidraw elements."""

    def test_parses_valid_elements(self):
        """Should parse valid legacy JSON with rectangle, text, and arrow elements."""
        response = json.dumps({
            "elements": [
                {
                    "id": "rect1",
                    "type": "rectangle",
                    "x": 100,
                    "y": 100,
                    "width": 200,
                    "height": 100,
                    "strokeColor": "#000000",
                    "backgroundColor": "#ffffff",
                    "fillStyle": "solid",
                },
                {
                    "id": "text1",
                    "type": "text",
                    "x": 150,
                    "y": 130,
                    "width": 100,
                    "height": 40,
                    "text": "Start",
                    "fontSize": 16,
                },
                {
                    "id": "arrow1",
                    "type": "arrow",
                    "x": 300,
                    "y": 150,
                    "width": 100,
                    "height": 0,
                    "startBinding": {"elementId": "rect1"},
                    "endBinding": {"elementId": "rect2"},
                },
            ],
            "description": "A simple flowchart showing the start state.",
        })

        result = parse_diagram_response(response)

        assert "elements" in result
        assert "description" in result
        assert len(result["elements"]) == 3
        assert result["elements"][0]["type"] == "rectangle"
        assert result["elements"][1]["type"] == "text"
        assert result["elements"][1]["label"]["text"] == "Start"
        assert result["elements"][2]["type"] == "arrow"
        assert result["elements"][2]["start"]["id"] == "rect1"
        assert result["elements"][2]["end"]["id"] == "rect2"
        assert result["description"] == "A simple flowchart showing the start state."

    def test_assigns_missing_ids(self):
        """Elements without IDs should get random IDs assigned."""
        response = json.dumps({
            "elements": [
                {
                    "type": "rectangle",
                    "x": 100,
                    "y": 100,
                    "width": 200,
                    "height": 100,
                },
                {
                    "type": "text",
                    "x": 150,
                    "y": 130,
                    "text": "Hello",
                },
            ],
        })

        result = parse_diagram_response(response)

        assert len(result["elements"]) == 2
        # Both should have IDs now
        assert "id" in result["elements"][0]
        assert "id" in result["elements"][1]
        # IDs should be non-empty strings
        assert isinstance(result["elements"][0]["id"], str)
        assert len(result["elements"][0]["id"]) > 0
        # IDs should be unique
        assert result["elements"][0]["id"] != result["elements"][1]["id"]

    def test_handles_invalid_json(self):
        """Should return empty elements on invalid JSON."""
        response = "This is not valid JSON {broken"

        result = parse_diagram_response(response)

        assert "elements" in result
        assert result["elements"] == []
        assert result.get("description") is None

    def test_handles_json_without_elements_key(self):
        """Should handle JSON that doesn't have an 'elements' key."""
        response = json.dumps({"description": "Some text"})

        result = parse_diagram_response(response)

        assert result["elements"] == []
        assert result["description"] == "Some text"

    def test_layouts_zero_coordinate_legacy_elements(self):
        """Legacy elements at (0,0) should get generated positions."""
        response = json.dumps({
            "elements": [
                {"id": "a", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "b", "type": "ellipse", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "c", "type": "diamond", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "d", "type": "text", "x": 0, "y": 0, "text": "Label"},
            ],
        })

        result = parse_diagram_response(response)

        for elem in result["elements"]:
            if elem["type"] not in ("arrow", "line"):
                assert elem["x"] > 0 or elem["y"] > 0, f"Element {elem['id']} still at (0,0)"

    def test_preserves_explicit_coordinates(self):
        """Elements with explicit coordinates should not be modified."""
        response = json.dumps({
            "elements": [
                {"id": "a", "type": "rectangle", "x": 50, "y": 75, "width": 100, "height": 80},
                {"id": "b", "type": "ellipse", "x": 200, "y": 300, "width": 100, "height": 80},
            ],
        })

        result = parse_diagram_response(response)

        # Coordinates should be preserved
        assert result["elements"][0]["x"] == 50
        assert result["elements"][0]["y"] == 75
        assert result["elements"][1]["x"] == 200
        assert result["elements"][1]["y"] == 300
