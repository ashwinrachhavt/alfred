from __future__ import annotations

import pytest
from pydantic import SecretStr


def test_encrypt_decrypt_json_roundtrip() -> None:
    from alfred.core.settings import settings

    settings.secret_key = SecretStr("test-secret")

    from alfred.core.crypto import decrypt_json, encrypt_json

    data = {"hello": "world", "n": 1}
    encrypted = encrypt_json(data, aad=b"aad")
    decrypted = decrypt_json(encrypted, aad=b"aad")

    assert decrypted == data


def test_decrypt_rejects_wrong_aad() -> None:
    from alfred.core.settings import settings

    settings.secret_key = SecretStr("test-secret")

    from alfred.core.crypto import decrypt_json, encrypt_json

    encrypted = encrypt_json({"k": "v"}, aad=b"aad-1")
    with pytest.raises(Exception):
        decrypt_json(encrypted, aad=b"aad-2")
