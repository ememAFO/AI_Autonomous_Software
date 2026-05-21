# Payment Boundaries

Stripe handles billing.

Agents may:
- integrate Stripe SDKs
- generate billing UI

Agents may not:
- access production Stripe secrets
- issue refunds automatically
- change billing logic
