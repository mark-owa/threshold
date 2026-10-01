import jwt
import pytest

from app.core.config import get_settings
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
    token = create_access_token(subject="user-123", expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


@pytest.mark.parametrize("claim", ["exp", "iat", "nbf"])
@pytest.mark.parametrize("value", [None, [], {}])
def test_jwt_malformed_time_claim_rejected_as_token_error(claim, value):
    payload = decode_token(create_access_token(subject="user-123"))
    payload[claim] = value
    token = jwt.encode(payload, get_settings().SECRET_KEY, algorithm="HS256")

    # Malformed claims must use the documented JWT error hierarchy.
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


@pytest.mark.parametrize(
    ("claim", "value", "error"),
    [
        ("iss", "untrusted-issuer", jwt.InvalidIssuerError),
        ("aud", "another-application", jwt.InvalidAudienceError),
    ],
)
def test_jwt_wrong_issuer_or_audience_rejected(claim, value, error):
    payload = decode_token(create_access_token(subject="user-123"))
    payload[claim] = value
    token = jwt.encode(payload, get_settings().SECRET_KEY, algorithm="HS256")

    with pytest.raises(error):
        decode_token(token)


@pytest.mark.parametrize("algorithm", ["HS384", "none"])
def test_jwt_unapproved_algorithm_rejected(algorithm):
    payload = decode_token(create_access_token(subject="user-123"))
    key = None if algorithm == "none" else get_settings().SECRET_KEY
    token = jwt.encode(payload, key, algorithm=algorithm)

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_token(token)


def test_jwt_wrong_signature_rejected():
    payload = decode_token(create_access_token(subject="user-123"))
    token = jwt.encode(payload, "different-test-signing-key-with-32-bytes", algorithm="HS256")

    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token)


def test_jwt_options_reuse_cannot_disable_expiry_validation():
    settings = get_settings()
    token = create_access_token(subject="user-123", expires_minutes=-1)
    options = {"verify_signature": False}
    jwt.decode(token, options=options)
    assert options == {"verify_signature": False}

    # Regression for GHSA-gvp8-978c-rx2q: an unverified read must not leave
    # claim validation disabled when the same options mapping is reused.
    options["verify_signature"] = True
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options=options,
        )


def test_password_verification_handles_bcrypt_byte_limit_and_bad_hash():
    hashed = hash_password("demo1234")
    assert not verify_password("x" * 73, hashed)
    assert not verify_password("é" * 40, hashed)
    assert not verify_password("demo1234", "malformed")
