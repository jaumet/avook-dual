# Development Roadmap Checklist

- [x] Define and document the full magic link authentication flow.
- [x] Provision database schema for `users` and `magic_link_tokens` tables.
- [x] Implement security rules (single-use tokens, hashing, expiration, optional IP/UA logging, and rate limiting hooks).
- [x] Handle Stripe checkout webhooks to upsert users with full access.
- [x] Build `POST /auth/magic-link/request` endpoint to generate and email tokens.
- [x] Build `GET /auth/magic-login` endpoint to validate tokens and issue JWTs.
- [x] Document environment variables, dependencies, and local development instructions.
