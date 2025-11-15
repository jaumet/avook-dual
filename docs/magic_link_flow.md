# Magic Link Login Flow

This document summarizes the secure passwordless login flow that Audiovook Dual should support. It is ready to hand to Codex / "Jules" to implement the FastAPI + Postgres backend logic.

## 1. Overview

Actors involved:

- **Stripe** handles the checkout flow and shares the customer's email via webhooks.
- **Audiovook backend** (FastAPI, Postgres, JWT) stores users and issues access tokens.
- **User** only needs to remember their email address.

High-level flow:

1. **Stripe purchase**
   - Stripe sends a webhook to the backend.
   - The backend creates or updates the `User` with `full_access = true` using the Stripe email.
2. **User requests access**
   - The user submits their email to a simple form.
   - The frontend calls `POST /auth/magic-link/request`.
3. **Backend issues a magic link**
   - Generates a long random token and only stores its SHA-256 hash.
   - Records expiration, IP, user-agent, and sets `used_at = NULL`.
   - Sends an email that points to `https://audiovook.com/auth/magic-login?token=<RAW_TOKEN>`.
4. **User clicks the magic link**
   - Browser opens `GET /auth/magic-login?token=...`.
   - Backend validates the hash, expiry, `used_at`, optional IP/UA, and that the user is active.
   - Marks the token as used and generates a JWT.
   - Returns the JWT in an `HttpOnly` cookie or JSON so the frontend can store it.
5. **Authenticated usage**
   - All protected routes (e.g., `/api/abook/...`) continue validating JWTs as they do today.

## 2. Database schema

Users table (simplified reference):

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_access BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Magic link tokens table:

```sql
CREATE TABLE magic_link_tokens (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_ip TEXT,
    created_user_agent TEXT
);
CREATE INDEX idx_magic_link_tokens_user ON magic_link_tokens(user_id);
CREATE INDEX idx_magic_link_tokens_token_hash ON magic_link_tokens(token_hash);
```

## 3. Security rules

1. **Single use tokens** — Only valid when `used_at IS NULL`, and mark as used immediately.
2. **Short expiration** — Set `expires_at = now() + interval '15 minutes'` (or 5/10 minutes).
3. **Hash only** — Store `SHA-256(raw_token)` in the database, never the raw token.
4. **Optional IP / UA checks** — Record `created_ip` and `created_user_agent` and optionally validate at consumption time.
5. **Rate limiting per email** — e.g., no more than 5 magic links per hour per email (can be added later).

## 4. Stripe webhook to grant access

FastAPI skeleton:

```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        customer_email = data.get("customer_details", {}).get("email")
        if customer_email:
            upsert_user_with_full_access(db, customer_email)
    return {"ok": True}
```

Helper:

```python
def upsert_user_with_full_access(db, email: str):
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user:
        user = User(email=email_norm, full_access=True, is_active=True)
        db.add(user)
    else:
        user.full_access = True
        user.is_active = True
    db.commit()
    db.refresh(user)
    return user
```

## 5. `POST /auth/magic-link/request`

- **Body**:

```json
{ "email": "user@example.com" }
```

- **Response** (always the same, to avoid leaking which emails exist):

```json
{ "detail": "If this email is registered, a login link has been sent." }
```

- **Logic**:
  1. Normalize email and lookup active user with `full_access = true`.
  2. If user missing or not allowed, return the generic response.
  3. Generate a 32-byte url-safe token, hash it with SHA-256.
  4. Create `magic_link_tokens` row with 15-minute expiry, metadata, and `used_at = NULL`.
  5. Email the link: `https://audiovook.com/auth/magic-login?token=<RAW_TOKEN>`.

Helper snippets:

```python
def generate_magic_raw_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
```

## 6. `GET /auth/magic-login`

- **Query**: `token=<RAW_TOKEN>`
- **Validation**:
  - Hash the token and fetch the matching row.
  - Reject if missing, expired, already used, or associated user inactive / without access.
  - Optionally compare IP / UA with recorded values.
- **Success**:
  - Mark the magic link token as used.
  - Issue a JWT with the user id in `sub`.
  - Return either JSON `{access_token, token_type, user}` or set the JWT in an `HttpOnly` cookie and redirect.

Example JSON response handler:

```python
@router.get("/auth/magic-login")
async def magic_login(token: str = Query(...)):
    token_hash = hash_token(token)
    ml = db.query(MagicLinkToken).filter(MagicLinkToken.token_hash == token_hash).first()
    # validate ml + user, mark used, generate JWT
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_access": user.full_access}
    }
```

## 7. Integration notes

- Existing JWT-protected endpoints remain unchanged.
- The only difference is how users obtain their JWTs: via the magic link flow instead of passwords.
- Optional enhancements: email templates (Catalan / English), cookie-based login with redirect, rate limiting, and suspicious login detection using IP/UA deltas.
