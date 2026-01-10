from __future__ import annotations

from pathlib import Path

from alfred.prompts import load_prompt


def test_all_prompt_templates_load_and_are_non_empty() -> None:
    prompts_root = Path(__file__).resolve().parents[3] / "apps" / "alfred" / "prompts"
    assert prompts_root.exists(), "apps/alfred/prompts directory missing"

    for path in prompts_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".md", ".txt"}:
            continue

        rel_parts = path.relative_to(prompts_root).parts
        content = load_prompt(*rel_parts)
        assert content.strip(), f"Prompt template is empty: {path}"
