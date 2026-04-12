from __future__ import annotations

import json

from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response


def test_build_diagram_prompt_includes_context_and_generic_diagram_guidance() -> None:
    prompt = build_diagram_prompt(
        "visualize the onboarding journey",
        'Canvas: "Growth map"\nVisible labels: Landing page, Signup',
    )

    assert "visualize the onboarding journey" in prompt
    assert 'Canvas: "Growth map"' in prompt
    assert "mind map" in prompt
    assert "user flow / journey" in prompt
    assert '"nodes"' in prompt
    assert '"edges"' in prompt


def test_parse_diagram_response_builds_elements_from_graph_spec() -> None:
    response = json.dumps(
        {
            "diagram_type": "flowchart",
            "layout": "horizontal",
            "description": "Maps the request flow.",
            "nodes": [
                {"id": "start", "label": "Start", "kind": "start"},
                {"id": "decide", "label": "Valid input?", "kind": "decision"},
                {"id": "done", "label": "Done", "kind": "end"},
            ],
            "edges": [
                {"from": "start", "to": "decide"},
                {"from": "decide", "to": "done", "label": "yes", "kind": "conditional"},
            ],
        }
    )

    result = parse_diagram_response(response)

    node_elements = [element for element in result["elements"] if element["type"] != "arrow"]
    arrow_elements = [element for element in result["elements"] if element["type"] == "arrow"]

    assert result["description"] == "Maps the request flow."
    assert len(node_elements) == 3
    assert len(arrow_elements) == 2
    assert next(element for element in node_elements if element["id"] == "decide")["type"] == "diamond"
    labeled_edge = next(
        element
        for element in arrow_elements
        if isinstance(element.get("label"), dict) and element["label"].get("text") == "yes"
    )
    assert labeled_edge["strokeStyle"] == "dashed"
    assert all(element["x"] != 0 or element["y"] != 0 for element in node_elements)


def test_parse_diagram_response_accepts_code_fenced_json() -> None:
    response = """```json
    {
      "diagram_type": "mindmap",
      "layout": "radial",
      "nodes": [
        {"id": "core", "label": "Core idea", "kind": "concept"},
        {"id": "branch", "label": "Branch", "kind": "concept"}
      ],
      "edges": [
        {"from": "core", "to": "branch"}
      ]
    }
    ```"""

    result = parse_diagram_response(response)

    assert len(result["elements"]) == 3
    assert result["description"] == "Created a mind map with 2 structured nodes."


def test_parse_diagram_response_normalizes_legacy_element_payloads() -> None:
    response = json.dumps(
        {
            "diagram_type": "flowchart",
            "layout": "horizontal",
            "elements": [
                {"id": "alpha", "type": "rectangle", "x": 0, "y": 0, "text": "Alpha"},
                {"id": "beta", "type": "rectangle", "x": 0, "y": 0, "text": "Beta"},
                {
                    "id": "link-1",
                    "type": "arrow",
                    "startBinding": {"elementId": "alpha"},
                    "endBinding": {"elementId": "beta"},
                },
            ],
        }
    )

    result = parse_diagram_response(response)

    alpha = next(element for element in result["elements"] if element["id"] == "alpha")
    arrow = next(element for element in result["elements"] if element["type"] == "arrow")

    assert alpha["label"]["text"] == "Alpha"
    assert alpha["x"] != 0 or alpha["y"] != 0
    assert arrow["start"]["id"] == "alpha"
    assert arrow["end"]["id"] == "beta"
