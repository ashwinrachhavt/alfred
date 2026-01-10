from __future__ import annotations

import base64

from alfred.services.llm_service import LLMService


class _Image:
    def __init__(self, *, b64_json: str, revised_prompt: str | None = None) -> None:
        self.b64_json = b64_json
        self.revised_prompt = revised_prompt


class _ImagesResponse:
    def __init__(self, data: list[object]) -> None:
        self.data = data


class _ImagesAPI:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, object] | None = None

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = dict(kwargs)
        if "response_format" in kwargs:
            raise AssertionError("generate_image_png must not send response_format")
        raw = b"\x89PNG\r\n\x1a\nstub"
        return _ImagesResponse(
            [_Image(b64_json=base64.b64encode(raw).decode(), revised_prompt=None)]
        )


class _OpenAIClient:
    def __init__(self) -> None:
        self.images = _ImagesAPI()


def test_generate_image_png_does_not_send_response_format() -> None:
    stub = _OpenAIClient()
    svc = LLMService(openai_client=stub)  # type: ignore[arg-type]

    img, revised = svc.generate_image_png(prompt="hello", model="gpt-image-1")
    assert img.startswith(b"\x89PNG\r\n\x1a\n")
    assert revised is None
    assert stub.images.last_kwargs is not None
    assert "response_format" not in stub.images.last_kwargs
