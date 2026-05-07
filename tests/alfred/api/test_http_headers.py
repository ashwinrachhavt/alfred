from alfred.api.http_headers import inline_content_disposition


def test_inline_content_disposition_supports_unicode_filenames() -> None:
    header = inline_content_disposition("Screenshot 2026-05-06 at 9.35.47\u202fPM.png")

    assert header.startswith('inline; filename="Screenshot 2026-05-06 at 9.35.47PM.png"')
    assert "filename*=UTF-8''Screenshot%202026-05-06%20at%209.35.47%E2%80%AFPM.png" in header
