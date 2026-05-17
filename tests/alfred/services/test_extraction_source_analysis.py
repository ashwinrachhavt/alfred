from __future__ import annotations

from typing import Any

from alfred.services import extraction_service as extraction_mod
from alfred.services.extraction_service import ExtractionService


class _FakeLLM:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] | None = None

    def structured(self, messages: list[dict[str, str]], schema: type[Any]) -> Any:
        self.messages = messages
        return schema(
            lang="en",
            summary_short="Software value is shifting away from undifferentiated SaaS.",
            summary_long="The article argues that software markets are developing a smile curve.",
            bullets=["Value moves to scarce distribution and services."],
            key_points=["Software middle layers are commoditizing."],
            topics_primary="software_strategy",
            topics_secondary=["saas"],
            tags=["software", "strategy"],
            source_thesis="Software now has a smile curve.",
            source_argument_flow=[
                "Hardware value migrated to design and distribution.",
                "Software is now showing the same pattern.",
            ],
            source_audience="Software founders and operators",
        )


def test_extract_all_adds_source_analysis_from_capture_metadata(monkeypatch) -> None:
    monkeypatch.setattr(extraction_mod, "_LANGEXTRACT_AVAILABLE", False)
    monkeypatch.setattr(extraction_mod, "lx", None)
    llm = _FakeLLM()

    result = ExtractionService(llm_service=llm).extract_all(
        cleaned_text="The article explains how the smile curve applies to software.",
        raw_markdown="# The Smile Curve\n\n## The Same Curve\n\nBody",
        metadata={
            "source_capture": {
                "kind": "blog_article",
                "platform": "substack",
                "author": "Ryan Waliany",
                "headings": [
                    {"level": 1, "text": "The Smile Curve"},
                    {"level": 2, "text": "The Same Curve"},
                ],
            }
        },
        include_embedding=False,
        include_graph=False,
    )

    assert result["source_analysis"] == {
        "kind": "blog_article",
        "platform": "substack",
        "author": "Ryan Waliany",
        "thesis": "Software now has a smile curve.",
        "argument_flow": [
            "Hardware value migrated to design and distribution.",
            "Software is now showing the same pattern.",
        ],
        "audience": "Software founders and operators",
        "structure": ["The Smile Curve", "The Same Curve"],
    }
    assert llm.messages is not None
    assert "Captured source context" in llm.messages[1]["content"]
    assert "blog_article" in llm.messages[1]["content"]
