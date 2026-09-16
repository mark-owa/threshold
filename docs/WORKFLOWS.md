# Workflows

The seeded refund definition runs classify, extract, policy lookup, business rules,
risk assessment, approval gate, action execution, and verification in that order.

Eligible refunds up to and including the automatic threshold execute locally.
High amounts, policy failures, and missing fields pause for review. Approval or
modification invokes the refund action; rejection cancels the workflow. Invalid
modified action parameters produce a failed workflow with no refund action.

Customer, lead, support, and invoice/order definitions each classify the message
and append a mock email notification. No actual message is sent, lead scored, CRM
record updated, or invoice processed.

The failure scenario creates a fresh demo order and injects one timeout. Its failed
workflow retains a retryable action; manual retry or the scheduled task records a
successful retry and verification using that same action row. A different order
per failure demonstration keeps it independent of earlier successful refunds.
