"""Run deterministic AI-boundary evaluations without a database."""

from __future__ import annotations

import json
from pathlib import Path

from app.workflows.primitives import classify_text, extract_refund

BASE = Path(__file__).resolve().parents[1] / "evals"


def classification_eval(path: Path) -> tuple[int, int, dict[str, dict[str, int]]]:
    rows = json.loads(path.read_text())
    correct = 0
    confusion: dict[str, dict[str, int]] = {}
    for row in rows:
        predicted = classify_text(row["text"]).value
        expected = row["expected_category"]
        confusion.setdefault(expected, {}).setdefault(predicted, 0)
        confusion[expected][predicted] += 1
        correct += predicted == expected
    return correct, len(rows), confusion


def extraction_eval(path: Path) -> tuple[int, int]:
    rows = json.loads(path.read_text())
    correct = 0
    for row in rows:
        predicted = extract_refund(row["text"])
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
    return correct, len(rows)


def main() -> int:
    base_correct, base_total, base_confusion = classification_eval(BASE / "dataset.json")
    adv_correct, adv_total, adv_confusion = classification_eval(BASE / "adversarial.json")
    ext_correct, ext_total = extraction_eval(BASE / "extraction.json")

    base_acc = base_correct / base_total if base_total else 0.0
    adv_acc = adv_correct / adv_total if adv_total else 0.0
    ext_acc = ext_correct / ext_total if ext_total else 0.0

    print(f"base_classification={base_correct}/{base_total} accuracy={base_acc:.3f}")
    print(f"adversarial_classification={adv_correct}/{adv_total} accuracy={adv_acc:.3f}")
    print(f"refund_extraction={ext_correct}/{ext_total} accuracy={ext_acc:.3f}")
    print("base_confusion_matrix=")
    print(json.dumps(base_confusion, indent=2, sort_keys=True))
    print("adversarial_confusion_matrix=")
    print(json.dumps(adv_confusion, indent=2, sort_keys=True))

    return 0 if min(base_acc, adv_acc, ext_acc) >= 0.90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
