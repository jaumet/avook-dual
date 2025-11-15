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
- `GET /auth/magic-login?token=<RAW_TOKEN>` – validates a magic link token and returns a signed JWT.
- `POST /webhooks/stripe` – consumes Stripe checkout events and grants `full_access` to matching users.

All state is stored using SQLAlchemy models for `users` and `magic_link_tokens`, matching the schema from the documentation.
