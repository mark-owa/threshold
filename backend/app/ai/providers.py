from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models.enums import RequestCategory
from app.workflows.primitives import classify_text, extract_refund


class ClassificationResult(BaseModel):
    category: RequestCategory
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


class RefundExtractionResult(BaseModel):
    order_number: str | None = None
    amount_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)


@dataclass(frozen=True)
class AIResult:
    value: BaseModel
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


class AIProvider(Protocol):
    name: str

    def classify(
        self, *, text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult: ...

    def extract_refund(
        self, *, text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult: ...


class MockAIProvider:
    name = "mock"

    def classify(self, *, text: str, model: str, system_prompt: str, user_prompt: str) -> AIResult:
        started = time.perf_counter()
        category = classify_text(text)
        value = ClassificationResult(
            category=category, confidence=0.96, rationale="Deterministic demo classifier."
        )
        return AIResult(
            value,
            self.name,
            model,
            max(1, len(user_prompt.split())),
            1,
            0.0,
            int((time.perf_counter() - started) * 1000),
        )

    def extract_refund(
        self, *, text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult:
        started = time.perf_counter()
        extracted = extract_refund(text)
        value = RefundExtractionResult(**extracted)
        return AIResult(
            value,
            self.name,
            model,
            max(1, len(user_prompt.split())),
            1,
            0.0,
            int((time.perf_counter() - started) * 1000),
        )


T = TypeVar("T", bound=BaseModel)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def _parse(
        self, *, schema: type[T], text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult:
        started = time.perf_counter()
        response = self.client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt.format(text=text)},
            ],
            response_format=schema,
        )
        message = response.choices[0].message
        if not message.parsed:
            raise ValueError("Provider returned no structured result")
        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return AIResult(
            message.parsed,
            self.name,
            model,
            prompt_tokens,
            completion_tokens,
            _estimate_cost(model, prompt_tokens, completion_tokens),
            int((time.perf_counter() - started) * 1000),
        )

    def classify(self, *, text: str, model: str, system_prompt: str, user_prompt: str) -> AIResult:
        return self._parse(
            schema=ClassificationResult,
            text=text,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def extract_refund(
        self, *, text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult:
        return self._parse(
            schema=RefundExtractionResult,
            text=text,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str):
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)

    def _tool_call(
        self,
        *,
        schema: type[T],
        tool_name: str,
        text: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AIResult:
        started = time.perf_counter()
        response = self.client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt.format(text=text)}],
            tools=[
                {
                    "name": tool_name,
                    "description": "Return only the structured data requested by the system.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        tool_use = next(
            (block for block in response.content if getattr(block, "type", None) == "tool_use"),
            None,
        )
        if tool_use is None:
            raise ValueError("Provider returned no structured tool result")
        value = schema.model_validate(tool_use.input)
        usage = response.usage
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return AIResult(
            value,
            self.name,
            model,
            prompt_tokens,
            completion_tokens,
            _estimate_cost(model, prompt_tokens, completion_tokens),
            int((time.perf_counter() - started) * 1000),
        )

    def classify(self, *, text: str, model: str, system_prompt: str, user_prompt: str) -> AIResult:
        return self._tool_call(
            schema=ClassificationResult,
            tool_name="classify_request",
            text=text,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def extract_refund(
        self, *, text: str, model: str, system_prompt: str, user_prompt: str
    ) -> AIResult:
        return self._tool_call(
            schema=RefundExtractionResult,
            tool_name="extract_refund",
            text=text,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    provider = settings.AI_PROVIDER.lower()
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("AI_PROVIDER=openai but OPENAI_API_KEY is not configured")
        return OpenAIProvider(settings.OPENAI_API_KEY)
    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is not configured")
        return AnthropicProvider(settings.ANTHROPIC_API_KEY)
    if provider != "mock":
        raise ValueError(f"Unsupported AI_PROVIDER: {provider}")
    return MockAIProvider()


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    # Approximate USD pricing intentionally kept in one place and exposed as an estimate.
    pricing = {
        "gpt-4o-mini": (0.00015, 0.00060),
        "gpt-4o": (0.00500, 0.01500),
        "claude-3-5-sonnet-latest": (0.00300, 0.01500),
    }
    input_per_token, output_per_token = pricing.get(model, (0.0, 0.0))
    return round(
        prompt_tokens * input_per_token / 1000 + completion_tokens * output_per_token / 1000, 8
    )
