# AI evaluation

The deterministic evaluator scores 12 base classification examples, 8 adversarially
worded classification examples, and 5 refund extraction examples. It prints
accuracy and classification confusion matrices, and exits nonzero if any dataset
scores below 90%. The mock provider uses the same deterministic primitives.

The extraction score is whole-example exact match for order and amount, with a
numeric tolerance. Missing values must stay missing. Additional regression cases
check thousands separators and reject silently truncated decimal amounts.

This is a small regression dataset, not evidence of broad language understanding
or resistance to prompt injection. It does not measure confidence calibration,
customer/order ownership, or live-provider hallucination rates. Mock confidence is
a fixed illustrative value.

The optional live evaluator uses the same datasets and Pydantic schemas. Cost
figures use a small static lookup and are estimates; unknown models report zero,
which should not be interpreted as a free API call.
