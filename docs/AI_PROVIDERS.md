# AI Provider Architecture

Threshold keeps the model boundary behind a small provider interface:

`MockAIProvider` → deterministic local behavior for demos/tests

`OpenAIProvider` → structured outputs validated directly into Pydantic models

`AnthropicProvider` → structured tool-use output validated into the same Pydantic models

The workflow engine does not branch on provider-specific SDK calls. It asks for a classification or extraction result and records provider, model, token counts, latency, and estimated cost in `ai_usage_logs`.

## Live provider mode

Set:

```text
AI_PROVIDER=openai
OPENAI_API_KEY=...
```

or:

```text
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
AI_MODEL=<model supported by your Anthropic account>
```

Then run:

```text
make eval-live
```

The live evaluator uses the same labeled datasets as the deterministic evaluation harness. This gives the portfolio a clean comparison between deterministic baseline behavior and provider-backed behavior.

OpenAI structured output parsing is used so model responses are validated against Pydantic schemas instead of being trusted as arbitrary JSON. Anthropic uses constrained tool output and the same Pydantic validation boundary.

## Safety boundary

The provider can classify and extract information, but it cannot directly select arbitrary actions or bypass policy. The workflow engine remains responsible for policy evaluation, risk gating, approval, idempotency, execution, and verification.

The seeded prompts target an OpenAI model. Set `AI_MODEL` to override their
model target when using another provider; an explicit workflow-step `model`
configuration takes precedence. Unknown provider names raise an error.
Live-provider calls were not made during this review.
