---
name: PayPal webhook refunds
description: PayPal Payments v2 webhook resource shapes for capture refunds.
---

For `PAYMENT.CAPTURE.REFUNDED`, PayPal sends a capture resource; its `resource.id`
is the capture ID, not a refund ID. Reconcile through the server with
`GET /v2/payments/captures/{capture_id}` and use its cumulative
`seller_receivable_breakdown.total_refunded_amount`. The refund details endpoint
is appropriate only when the event actually supplies a refund ID.

**Why:** Assuming a capture-refund event contains a refund ID causes the wrong
Payments API endpoint to be queried and can misclassify a genuine refund.

**How to apply:** Confirm each webhook event’s resource schema in PayPal’s current
event-name documentation before choosing the server-side reconciliation endpoint.
