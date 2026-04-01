"""Excalidraw AI agent for generating diagrams from natural language."""

from __future__ import annotations

import json
import secrets
from typing import Any


def build_diagram_prompt(user_request: str, canvas_context: str | None = None) -> str:
    """Build an LLM prompt that instructs the model to output Excalidraw element JSON.

    Args:
        user_request: The user's natural language diagram request.
        canvas_context: Optional context about existing canvas elements.

    Returns:
        A prompt string that explains the Excalidraw format and includes the user's request.
    """
    context_section = ""
    if canvas_context:
        context_section = f"\n\n**Current canvas context:**\n{canvas_context}\n"

    prompt = f"""You are an expert at creating diagrams in Excalidraw format. Generate diagram elements based on the user's request.

{context_section}
**User request:**
{user_request}

**Excalidraw Element Format:**

Each element needs these fields:
- `id`: A unique random string (e.g., "elem-abc123")
- `type`: One of "rectangle", "ellipse", "diamond", "text", "arrow", "line"
- `x`, `y`: Top-left coordinates (numbers)
- `width`, `height`: Dimensions (numbers)
- `strokeColor`: Hex color (e.g., "#000000")
- `backgroundColor`: Hex color (e.g., "#ffffff")
- `fillStyle`: "solid", "hachure", or "cross-hatch"
- `strokeWidth`: Line width (default: 1)
- `roughness`: 0 (smooth) to 2 (rough), default 1
- `opacity`: 0 to 100, default 100

For **text** elements, add:
- `text`: The text content (string)
- `fontSize`: Font size (number, default 20)
- `textAlign`: "left", "center", "right" (default "left")

For **arrow** elements, add:
- `startBinding`: {{"elementId": "id-of-start-element"}} (optional)
- `endBinding`: {{"elementId": "id-of-end-element"}} (optional)

**Layout Guidelines:**
- If you don't specify exact coordinates, just use x=0, y=0 for all elements (auto-layout will handle it)
- Standard spacing: 250px horizontally, 150px vertically between elements
- Typical element sizes: rectangles 200×100, diamonds 180×120, text auto-sized
- For flowcharts: use rectangles for processes, diamonds for decisions, arrows to connect
- For architecture diagrams: use rectangles for components, arrows for connections, text for labels
- For mind maps: use ellipses for nodes, lines for connections

**Output Format:**

Return ONLY valid JSON in this exact format:

{{
  "elements": [
    {{
      "id": "elem-1",
      "type": "rectangle",
      "x": 0,
      "y": 0,
      "width": 200,
      "height": 100,
      "strokeColor": "#000000",
      "backgroundColor": "#ffffff",
      "fillStyle": "solid",
      "strokeWidth": 1,
      "roughness": 1,
      "opacity": 100
    }},
    {{
      "id": "elem-2",
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 100,
      "height": 40,
      "text": "Example",
      "fontSize": 20,
      "strokeColor": "#000000",
      "backgroundColor": "transparent",
      "fillStyle": "solid"
    }}
  ],
  "description": "Brief description of what you created"
}}

**Important:**
- Use ONLY the JSON format above
- Do NOT include markdown code blocks or explanatory text
- Generate 3-10 elements for a meaningful diagram
- Use appropriate colors and styles
- Connect related elements with arrows
"""
    return prompt


def auto_layout(
    elements: list[dict[str, Any]],
    start_x: int = 100,
    start_y: int = 100,
    col_width: int = 250,
    row_height: int = 150,
    cols: int = 3,
) -> list[dict[str, Any]]:
    """Assign grid positions to elements with zero or missing coordinates.

    Args:
        elements: List of Excalidraw elements.
        start_x: Starting X coordinate for the grid.
        start_y: Starting Y coordinate for the grid.
        col_width: Horizontal spacing between columns.
        row_height: Vertical spacing between rows.
        cols: Number of columns in the grid.

    Returns:
        The elements list with updated coordinates.
    """
    # Only layout non-arrow/line elements
    non_arrow = [e for e in elements if e.get("type") not in ("arrow", "line")]

    for i, elem in enumerate(non_arrow):
        if elem.get("x", 0) == 0 and elem.get("y", 0) == 0:
            row = i // cols
            col = i % cols
            elem["x"] = start_x + col * col_width
            elem["y"] = start_y + row * row_height

    return elements


def parse_diagram_response(response: str) -> dict[str, Any]:
    """Parse LLM response into Excalidraw elements.

    Validates elements, assigns IDs if missing, and applies auto-layout for zero coordinates.

    Args:
        response: Raw LLM response, expected to be JSON.

    Returns:
        Dictionary with "elements" (list) and optional "description" (string).
    """
    try:
        # Try to parse as JSON
        data = json.loads(response)
    except (json.JSONDecodeError, ValueError):
        # If not valid JSON, try to extract JSON from markdown code blocks
        if "```json" in response:
            try:
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
                data = json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                return {"elements": [], "description": None}
        elif "```" in response:
            try:
                json_start = response.index("```") + 3
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
                data = json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                return {"elements": [], "description": None}
        else:
            return {"elements": [], "description": None}

    # Extract elements and description
    elements = data.get("elements", [])
    description = data.get("description")

    # Assign IDs to elements that don't have them
    for elem in elements:
        if "id" not in elem or not elem["id"]:
            elem["id"] = f"elem-{secrets.token_hex(6)}"

    # Apply auto-layout to elements at (0, 0)
    elements = auto_layout(elements)

    return {
        "elements": elements,
        "description": description,
    }
