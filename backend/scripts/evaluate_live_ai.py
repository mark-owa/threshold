"""Optional provider-backed evaluation.

Requires AI_PROVIDER=openai or AI_PROVIDER=anthropic and the corresponding API key.
This runner never mutates business data; it only exercises classification/extraction
against the labeled local datasets and prints accuracy so a developer can compare
live-provider behavior with the deterministic baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ai.prompts import DEFAULT_PROMPTS
from app.ai.providers import get_ai_provider
from app.core.config import get_settings

BASE = Path(__file__).resolve().parents[1] / "evals"


def main() -> int:
    provider = get_ai_provider()
    if provider.name == "mock":
        print(
            "AI_PROVIDER=mock; live evaluation requires a configured OpenAI or Anthropic provider."
        )
        return 2

    base = json.loads((BASE / "dataset.json").read_text())
    adversarial = json.loads((BASE / "adversarial.json").read_text())
    extraction = json.loads((BASE / "extraction.json").read_text())

    def classify(rows):
        correct = 0
        for row in rows:
            result = provider.classify(
                text=row["text"],
                model=get_settings().AI_MODEL or DEFAULT_PROMPTS["classify_intent"]["model"],
                system_prompt=DEFAULT_PROMPTS["classify_intent"]["system"],
                user_prompt=DEFAULT_PROMPTS["classify_intent"]["user"],
            )
            correct += result.value.model_dump()["category"] == row["expected_category"]
        return correct, len(rows)

    base_correct, base_total = classify(base)
    adv_correct, adv_total = classify(adversarial)

    extraction_correct = 0
    for row in extraction:
        result = provider.extract_refund(
            text=row["text"],
            model=get_settings().AI_MODEL or DEFAULT_PROMPTS["extract_refund"]["model"],
            system_prompt=DEFAULT_PROMPTS["extract_refund"]["system"],
            user_prompt=DEFAULT_PROMPTS["extract_refund"]["user"],
        )
        predicted = result.value.model_dump(exclude_none=True)
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
        extraction_correct += ok

    print(f"provider={provider.name}")
    print(
        f"base_classification={base_correct}/{base_total} accuracy={base_correct / base_total:.3f}"
    )
    print(
        f"adversarial_classification={adv_correct}/{adv_total} "
        f"accuracy={adv_correct / adv_total:.3f}"
    )
    print(
        f"refund_extraction={extraction_correct}/{len(extraction)} "
        f"accuracy={extraction_correct / len(extraction):.3f}"
    )
    return (
        0
        if min(
            base_correct / base_total, adv_correct / adv_total, extraction_correct / len(extraction)
        )
        >= 0.90
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
