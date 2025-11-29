from __future__ import annotations

from datetime import datetime, timezone

from alfred.services.mind_palace.doc_storage import (
    _domain_from_url,
    _maybe_object_id,
    _sha256_hex,
    _start_of_day_utc,
    _token_count,
)
from bson import ObjectId


def test_start_of_day_handles_naive_and_aware():
    naive = datetime(2024, 5, 17, 13, 45, 0)
    aware = datetime(2024, 5, 17, 13, 45, 0, tzinfo=timezone.utc)
    d1 = _start_of_day_utc(naive)
    d2 = _start_of_day_utc(aware)
    assert d1 == datetime(2024, 5, 17, 0, 0, tzinfo=timezone.utc)
    assert d2 == datetime(2024, 5, 17, 0, 0, tzinfo=timezone.utc)


def test_domain_from_url_various():
    assert _domain_from_url("https://example.com/path?q=1") == "example.com"
    assert _domain_from_url("http://sub.domain.co.uk") == "sub.domain.co.uk"
    assert _domain_from_url(None) is None
    assert _domain_from_url("") is None


def test_token_count_basic():
    assert _token_count("a b  c\n d") == 4
    assert _token_count("") == 0


def test_sha256_hex_stable():
    s1 = _sha256_hex("hello")
    s2 = _sha256_hex("hello")
    assert s1 == s2
    assert len(s1) == 64


def test_maybe_object_id():
    oid = ObjectId()
    assert _maybe_object_id(str(oid)) == oid
    assert _maybe_object_id("not-an-oid") is None
    assert _maybe_object_id(None) is None

