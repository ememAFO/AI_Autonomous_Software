# Security Rules

Always review code as a senior security engineer.

Check for:
- SQL injection
- command injection
- XSS
- auth bypass
- broken object-level authorization
- race conditions
- insecure defaults
- secrets exposure
- unsafe file upload
- dependency risk
- scalability bottlenecks

Rules:
- Never build SQL strings manually.
- Use ORM or parameterized queries.
- Every backend route must check authentication.
- Every object access must check ownership or role.
- Use atomic transactions for payments, bookings, inventory, credits, balances, and subscriptions.
- Store secrets in environment variables.
- Keep DEBUG=false in production.
- Restrict CORS.
- Rate limit login, signup, password reset, and AI endpoints.
