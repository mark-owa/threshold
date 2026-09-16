import pytest

from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)


def test_password_hash_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert not verify_password("wrong-password", hashed)


def test_jwt_roundtrip():
    token = create_access_token(subject="user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_jwt_expired_token_rejected():
    import jwt as pyjwt

    token = create_access_token(subject="user-123", expires_minutes=-1)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token)


def test_password_verification_handles_bcrypt_byte_limit_and_bad_hash():
    hashed = hash_password("demo1234")
    assert not verify_password("x" * 73, hashed)
    assert not verify_password("é" * 40, hashed)
    assert not verify_password("demo1234", "malformed")
