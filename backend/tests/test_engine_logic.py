from app.models.enums import RequestCategory
from app.workflows.engine import WorkflowEngine


def test_classify_refund_variants():
    assert (
        WorkflowEngine._classify("I want a refund for order #ORD-1001")
        == RequestCategory.REFUND_REQUEST
    )
    assert WorkflowEngine._classify("You charged me twice") == RequestCategory.REFUND_REQUEST


def test_classify_unknown_as_customer_inquiry():
    assert (
        WorkflowEngine._classify("Can you tell me your store hours?")
        == RequestCategory.CUSTOMER_INQUIRY
    )


def test_extract_refund_order_and_amount():
    data = WorkflowEngine._extract_refund("Please refund order #ORD-1001 for $65.00")
    assert data == {"order_number": "ORD-1001", "amount_usd": 65.0}


def test_extract_missing_fields_does_not_guess():
    assert WorkflowEngine._extract_refund("I need my money back") == {"order_number": None}


def test_classification_eval_dataset():
    import json
    from pathlib import Path

    dataset = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "dataset.json").read_text()
    )
    correct = sum(
        WorkflowEngine._classify(row["text"]).value == row["expected_category"] for row in dataset
    )
    assert correct / len(dataset) >= 0.90


def test_adversarial_classification_eval_dataset():
    import json
    from pathlib import Path

    dataset = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "adversarial.json").read_text()
    )
    correct = sum(
        WorkflowEngine._classify(row["text"]).value == row["expected_category"] for row in dataset
    )
    assert correct / len(dataset) >= 0.90


def test_refund_extraction_eval_dataset():
    import json
    from pathlib import Path

    dataset = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "extraction.json").read_text()
    )
    correct = 0
    for row in dataset:
        predicted = WorkflowEngine._extract_refund(row["text"])
        ok = predicted.get("order_number") == row["order_number"]
        expected_amount = row.get("amount_usd")
        actual_amount = predicted.get("amount_usd")
        if expected_amount is None:
            ok = ok and actual_amount is None
        else:
            ok = (
                ok
                and actual_amount is not None
                and abs(float(actual_amount) - float(expected_amount)) < 1e-9
            )
        correct += ok
    assert correct / len(dataset) >= 0.90


def test_retry_backoff_is_bounded_and_exponential():
    assert WorkflowEngine.retry_delay_seconds(1) == 1
    assert WorkflowEngine.retry_delay_seconds(2) == 2
    assert WorkflowEngine.retry_delay_seconds(3) == 4
    assert WorkflowEngine.retry_delay_seconds(10) == 60
