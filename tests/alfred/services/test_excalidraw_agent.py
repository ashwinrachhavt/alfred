"""Tests for Excalidraw AI agent service."""

from __future__ import annotations

import json

from alfred.services.excalidraw_agent import (
    auto_layout,
    build_diagram_prompt,
    parse_diagram_response,
)


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
        """Prompt should explain the Excalidraw element format."""
        prompt = build_diagram_prompt("draw a simple diagram")

        # Check for key Excalidraw concepts
        assert "rectangle" in prompt.lower()
        assert "arrow" in prompt.lower()
        assert "text" in prompt.lower()
        assert "x" in prompt and "y" in prompt  # coordinates
        assert "width" in prompt.lower() and "height" in prompt.lower()
        assert "strokeColor" in prompt or "stroke" in prompt.lower()

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
        """Should parse valid JSON with rectangle, text, and arrow elements."""
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
        assert result["elements"][2]["type"] == "arrow"
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

    def test_auto_layouts_zero_coords(self):
        """Elements at (0,0) should get grid-layout positions."""
        response = json.dumps({
            "elements": [
                {"id": "a", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "b", "type": "ellipse", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "c", "type": "diamond", "x": 0, "y": 0, "width": 100, "height": 80},
                {"id": "d", "type": "text", "x": 0, "y": 0, "text": "Label"},
            ],
        })

        result = parse_diagram_response(response)

        # All elements should have non-zero positions after auto-layout
        for elem in result["elements"]:
            if elem["type"] not in ("arrow", "line"):
                assert elem["x"] > 0 or elem["y"] > 0, f"Element {elem['id']} still at (0,0)"

        # Check they're laid out in a grid pattern
        # First element should be at start position (100, 100)
        assert result["elements"][0]["x"] == 100
        assert result["elements"][0]["y"] == 100

        # Second element should be in next column (100 + 250, 100)
        assert result["elements"][1]["x"] == 350
        assert result["elements"][1]["y"] == 100

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


class TestAutoLayout:
    """Test the auto-layout helper function."""

    def test_layouts_elements_in_grid(self):
        """Should arrange elements in a grid pattern."""
        elements = [
            {"id": "a", "type": "rectangle", "x": 0, "y": 0},
            {"id": "b", "type": "rectangle", "x": 0, "y": 0},
            {"id": "c", "type": "rectangle", "x": 0, "y": 0},
            {"id": "d", "type": "rectangle", "x": 0, "y": 0},
        ]

        result = auto_layout(elements, start_x=100, start_y=100, col_width=250, row_height=150, cols=3)

        # First row: 3 elements
        assert result[0]["x"] == 100 and result[0]["y"] == 100
        assert result[1]["x"] == 350 and result[1]["y"] == 100
        assert result[2]["x"] == 600 and result[2]["y"] == 100
        # Second row: 1 element
        assert result[3]["x"] == 100 and result[3]["y"] == 250

    def test_skips_arrows_and_lines(self):
        """Should not reposition arrows and lines."""
        elements = [
            {"id": "a", "type": "rectangle", "x": 0, "y": 0},
            {"id": "arrow1", "type": "arrow", "x": 0, "y": 0},
            {"id": "b", "type": "rectangle", "x": 0, "y": 0},
            {"id": "line1", "type": "line", "x": 0, "y": 0},
        ]

        result = auto_layout(elements)

        # Rectangles should be repositioned
        assert result[0]["x"] > 0
        assert result[2]["x"] > 0
        # Arrow and line should stay at (0, 0)
        assert result[1]["x"] == 0 and result[1]["y"] == 0
        assert result[3]["x"] == 0 and result[3]["y"] == 0

    def test_preserves_non_zero_coordinates(self):
        """Should not modify elements that already have positions."""
        elements = [
            {"id": "a", "type": "rectangle", "x": 50, "y": 75},
            {"id": "b", "type": "rectangle", "x": 0, "y": 0},
        ]

        result = auto_layout(elements)

        # First element should keep its position
        assert result[0]["x"] == 50 and result[0]["y"] == 75
        # Second element should get laid out
        assert result[1]["x"] > 0 and result[1]["y"] > 0
