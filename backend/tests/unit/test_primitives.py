import pytest

from app.models.enums import RequestCategory
from app.workflows.primitives import (
    classify_text,
    extract_refund,
    normalize_payload,
    retry_delay_seconds,
)


def test_normalize_payload_prefers_text_and_strips_whitespace():
    assert normalize_payload({"message": "  hello  ", "sender": "a@example.com"}) == {
        "text": "hello",
        "sender": "a@example.com",
        "external_id": None,
    }


def test_normalize_payload_uses_body_fallback():
    assert normalize_payload({"body": "support needed"})["text"] == "support needed"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Please refund order #ORD-1001", RequestCategory.REFUND_REQUEST),
        ("I am interested and want a quote", RequestCategory.LEAD_INQUIRY),
        ("Where is my order?", RequestCategory.INVOICE_ORDER),
        ("The checkout is broken", RequestCategory.SUPPORT_REQUEST),
        ("What time do you open?", RequestCategory.CUSTOMER_INQUIRY),
    ],
)
def test_classification_is_deterministic(text, expected):
    assert classify_text(text) == expected


def test_refund_extraction_does_not_guess_missing_fields():
    assert extract_refund("Please refund my money") == {"order_number": None}


def test_refund_extraction_is_case_insensitive():
    assert extract_refund("refund ORDER: ord-7 for USD 12.50") == {
        "order_number": "ord-7",
        "amount_usd": 12.5,
    }


def test_retry_backoff_is_bounded():
    assert [retry_delay_seconds(i) for i in range(1, 7)] == [1, 2, 4, 8, 16, 32]
    assert retry_delay_seconds(10) == 60
    assert retry_delay_seconds(1, base=3) == 1


@pytest.mark.parametrize(
    "text,amount",
    [
        ("refund $1,000.50", 1000.5),
        ("refund $65.001", None),
        ("refund $-5", -5.0),
        ("refund -$5", -5.0),
        ("refund $1e3", None),
        ("refund $1,00", None),
    ],
)
def test_extraction_does_not_truncate_money(text, amount):
    assert extract_refund(text).get("amount_usd") == amount


def test_normalization_preserves_demo_failure_and_rejects_bad_metadata():
    assert (
        normalize_payload({"text": "refund", "simulate_failure_once": True})[
            "simulate_failure_once"
        ]
        is True
    )
    with pytest.raises(ValueError):
        normalize_payload({"text": {"unexpected": "object"}})
    with pytest.raises(ValueError):
        normalize_payload({"sender": ["not", "an", "email"]})
