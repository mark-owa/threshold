from app.ai.providers import ClassificationResult, MockAIProvider, RefundExtractionResult


def test_mock_provider_returns_schema_valid_classification():
    provider = MockAIProvider()
    result = provider.classify(
        text="Please refund order #ORD-1002 for $65.00",
        model="mock-classifier-v1",
        system_prompt="system",
        user_prompt="{text}",
    )
    assert isinstance(result.value, ClassificationResult)
    assert result.value.category.value == "refund_request"
    assert result.provider == "mock"
    assert result.cost_usd == 0


def test_mock_provider_returns_schema_valid_refund_extraction():
    provider = MockAIProvider()
    result = provider.extract_refund(
        text="Please refund order #ORD-1002 for $65.00",
        model="mock-extractor-v1",
        system_prompt="system",
        user_prompt="{text}",
    )
    assert isinstance(result.value, RefundExtractionResult)
    assert result.value.order_number == "ORD-1002"
    assert result.value.amount_usd == 65.0
