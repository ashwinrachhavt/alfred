from alfred_app.services.gmail import GmailService


def sample_message_full():
    return {
        "snippet": "Hello there",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "To", "value": "Bob <bob@example.com>"},
                {"name": "Subject", "value": "Greetings"},
                {"name": "Date", "value": "Fri, 13 Sep 2025 09:00:00 +0000"},
            ],
            "body": {"data": "PGRpdj5IZWxsbyBodG1sPC9kaXY+", "size": 22},
            "parts": [
                {
                    "partId": "1",
                    "mimeType": "text/plain",
                    "body": {"data": "SGVsbG8gdGV4dA", "size": 10},
                },
                {
                    "partId": "2",
                    "mimeType": "text/html",
                    "body": {"data": "PGRpdj5IZWxsbyBodG1sPC9kaXY", "size": 22},
                },
                {
                    "partId": "3",
                    "mimeType": "application/pdf",
                    "filename": "doc.pdf",
                    "body": {"attachmentId": "att-1", "size": 1234},
                },
            ],
        },
    }


def test_extract_plaintext_and_html():
    msg = sample_message_full()
    text = GmailService.extract_plaintext(msg)
    html = GmailService.extract_html(msg)
    assert "Hello" in (text or "")
    assert "Hello html" in (html or "")


def test_parse_headers_and_attachments():
    msg = sample_message_full()
    headers = GmailService.parse_headers(msg)
    assert headers.get("Subject") == "Greetings"
    atts = GmailService.list_attachments_from_message(msg)
    assert len(atts) == 1
    assert atts[0]["filename"] == "doc.pdf"
