# Magic Link Login Flow

This document summarizes the secure passwordless login flow that Audiovook Dual should support. It is ready to hand to Codex / "Jules" to implement the FastAPI + Postgres backend logic.

## 1. Overview

Actors involved:

- **PayPal** handles the checkout flow and shares the customer's email via IPN callbacks.
- **Audiovook backend** (FastAPI, Postgres, JWT) stores users and issues access tokens.
- **User** only needs to remember their email address.

High-level flow:

> **Note:** The production backend now grants per-package entitlements using `catalog/packages.json`. The legacy `full_access` flag is still supported for all-access plans, but PayPal purchases map to specific package IDs through the IPN `custom` field.

1. **PayPal purchase**
   - PayPal sends an IPN webhook to the backend once the payment is completed.
   - The backend creates or updates the `User` with the purchased package IDs using the PayPal email.
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
4. **IP + UA heuristics** — Record `created_ip` and `created_user_agent` and consider both deltas when rejecting suspicious logins to avoid false positives.
5. **Rate limiting per email** — No more than 5 magic links per hour per email (configurable via environment variables).
6. **Localized comms** — Send bilingual (Catalan/English) HTML + text emails so users instantly recognize the login request.

## 4. PayPal IPN to grant access

FastAPI skeleton:

```python
@router.post("/webhooks/paypal")
async def paypal_ipn(request: Request):
    payload = await request.body()
    verified = await verify_with_paypal(payload)  # POSTs `cmd=_notify-validate` back to PayPal
    if not verified:
        raise HTTPException(status_code=400, detail="Invalid IPN")

    params = parse_qs(payload.decode())
    payment_status = params.get("payment_status", [""])[0].lower()
    payer_email = params.get("payer_email", [""])[0]
    package_ids = params.get("custom", [""])[0].split(",")

    if payment_status == "completed" and payer_email and package_ids:
        upsert_user_packages(db, payer_email, package_ids)
    return {"ok": True}
```

Helper:

```python
def upsert_user_packages(db, email: str, package_ids: list[str]):
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user:
        user = User(email=email_norm, full_access=False, is_active=True)
        db.add(user)
    existing = set(user.packages)
    for package_id in package_ids:
        if package_id not in existing:
            user.package_links.append(UserPackage(package_id=package_id))
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
  - Return either JSON `{access_token, token_type, user}` or set the JWT in an `HttpOnly` cookie and redirect. The redirect target is validated against an allow-list to avoid open-redirect issues, and cookies inherit configurable `SameSite`, `Secure`, and `Domain` attributes.

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
- Optional enhancements now implemented: localized HTML emails, cookie-based login with redirect (including configurable cookie attributes and redirect allow-list), rate limiting, and suspicious login detection using combined IP/UA deltas. The frontend includes a polished login panel where users can request links, see status messages, and handle post-login redirects gracefully.
