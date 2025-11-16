# Development Roadmap Checklist

## Completed
- [x] Define and document the full magic link authentication flow.
- [x] Provision database schema for `users` and `magic_link_tokens` tables.
- [x] Implement core security rules (single-use tokens, hashing, expiration, optional IP/UA logging).
- [x] Handle Stripe checkout webhooks to upsert users with full access.
- [x] Build `POST /auth/magic-link/request` endpoint to generate and email tokens.
- [x] Build `GET /auth/magic-login` endpoint to validate tokens and issue JWTs.
- [x] Document environment variables, dependencies, and local development instructions.
- [x] Enforce per-email rate limiting on `POST /auth/magic-link/request`.
- [x] Expand suspicious-login heuristics (compare both IP and user-agent deltas before blocking).
- [x] Provide localized (Catalan/English) HTML email templates for magic link delivery.
- [x] Offer an HttpOnly cookie + redirect response option for `GET /auth/magic-login`.
- [x] Polish frontend UX so users can request links and handle redirects seamlessly.
- [x] Expose `/catalog/free` and `/catalog/premium` endpoints to split open and subscriber-only stories.
- [x] Update the catalog and player UI to consume the protected catalog automatically based on authentication state.

## TODO
All roadmap items from the initial scope are complete. Add new entries here as future needs arise.
