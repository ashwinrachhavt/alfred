from __future__ import annotations

from alfred.services.system_design_heuristics import template_library


def test_system_design_template_library_has_common_patterns() -> None:
    templates = template_library()
    assert len(templates) >= 15

    non_blank = [t for t in templates if t.id != "blank"]
    assert len(non_blank) >= 14

    for template in non_blank:
        mermaid = template.diagram.metadata.get("mermaid")
        assert isinstance(mermaid, str)
        assert mermaid.strip().startswith("flowchart")

