# avook-dual

Audiovook Dual now ships with a FastAPI backend that implements the secure magic-link flow described in `docs/magic_link_flow.md`.

## Backend quickstart

1. Create a Python virtual environment and install dependencies:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the example environment file and customize it:

   ```bash
   cp .env.example .env
   ```

   At minimum you must define `JWT_SECRET_KEY`, `DATABASE_URL`, `FRONTEND_MAGIC_LOGIN_URL`, and `STRIPE_WEBHOOK_SECRET`.

3. Initialize the database (SQLite will be created automatically if you keep the default `DATABASE_URL`).

4. Start the API:

   ```bash
   uvicorn backend.app:app --reload
   ```

The following routes are now available:

- `POST /auth/magic-link/request` – issues a one-time magic link token and emails it to the user.
- `GET /auth/magic-login?token=<RAW_TOKEN>` – validates a magic link token and returns a signed JWT. Pass `response_mode=cookie` to set the JWT inside an `HttpOnly` cookie and redirect to the configured `POST_LOGIN_REDIRECT_URL`.
- `POST /webhooks/stripe` – consumes Stripe checkout events and grants `full_access` to matching users.

- `GET /catalog/free` – returns the entries listed in `audios-free.json` for everyone (no authentication required).
- `GET /catalog/premium` – returns the private entries stored in `audios.json` for authenticated users with `full_access`.

All state is stored using SQLAlchemy models for `users` and `magic_link_tokens`, matching the schema from the documentation.

### Security hardening

- **Rate limiting**: `MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS` and `MAGIC_LINK_RATE_LIMIT_WINDOW_MINUTES` prevent excessive link generation per email.
- **Suspicious login heuristics**: The backend compares both IP and user-agent deltas before blocking to avoid false positives, with optional strict IP enforcement.
- **Cookie-based login**: When `response_mode=cookie`, tokens are set inside an `HttpOnly` cookie (configurable name, domain, SameSite, and Secure flags) and the user is redirected only if the host is on the allow-list defined in `ALLOWED_REDIRECT_HOSTS`.
- **Localized HTML emails**: Every login email now contains Catalan and English content plus a styled HTML button.

## Frontend login panel

`index.html` ships with a lightweight login panel where users can enter their email, submit the request, and see friendly status updates. The script automatically targets the backend hosted at `https://api.audiovook.com` in production (or `http://localhost:8000` for local development). To point to a different backend without rebuilding the page, set `window.__AUDIOVOOK_API__` before the script executes:

```html
<script>
  window.__AUDIOVOOK_API__ = "https://staging-api.audiovook.com";
</script>
```

After a successful cookie-based login the backend redirects back to `/?login=ok`, triggering a toast that confirms the session is ready.
