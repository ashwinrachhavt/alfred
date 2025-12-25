from __future__ import annotations

from alfred.services.interview_service import InterviewDetectionService


def test_is_interview_candidate_flags_keyword_hits() -> None:
    detector = InterviewDetectionService()
    assert detector.is_interview_candidate(
        subject="Phone screen at Acme",
        email_text="Let's schedule your interview for next week.",
    )


def test_detect_extracts_company_role_type_and_meeting_link() -> None:
    detector = InterviewDetectionService()
    body = """
    Hi,

    Your phone screen is scheduled for January 20, 2026 at 10:00 AM PT.
    Join: https://zoom.us/j/123456789
    """
    det = detector.detect(
        subject="Interview at Acme — Phone Screen for Backend Engineer",
        email_text=body,
        company_hint=None,
        role_hint=None,
    )

    assert det.company == "Acme"
    assert det.role == "Backend Engineer"
    assert det.interview_type == "phone_screen"
    assert det.interview_date is not None
    assert det.meeting_links == ["https://zoom.us/j/123456789"]
