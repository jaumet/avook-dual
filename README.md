# avook-dual

Audiovook Dual now ships with a FastAPI backend that implements the secure magic-link flow described in `docs/magic_link_flow.md`.

## Docker quickstart

1. Copy the backend environment template and set at least `JWT_SECRET_KEY` plus the frontend URLs you want to use. You can keep
   the SMTP fields empty for local testing—the API logs the magic link URL whenever email delivery is disabled.

   ```bash
   cp backend/.env.example backend/.env
   ```

2. Build and start both the FastAPI backend and the static frontend:

   ```bash
   docker compose up --build
   ```

   * Backend → <http://localhost:8000>
   * Frontend → <http://localhost:6060>

   The compose file automatically points the backend to a SQLite database stored in the named volume `backend-data`. The file is
   created the first time the container boots, so you do not need to provision anything manually.

3. Create or inspect subscribers directly inside the running image:

   ```bash
   docker compose run --rm backend python -m backend.manage create-user you@example.com --full-access
   docker compose run --rm backend python -m backend.manage list-users
   ```

   After requesting a magic link from the browser you will see the login URL printed in the backend logs. Copy it into the
   browser, append `&response_mode=cookie` if you want an HttpOnly session cookie, and the premium catalog will unlock.

Stop everything at any time with `docker compose down` (add `-v` if you also want to delete the SQLite volume).

## Manual backend quickstart

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

   At minimum you must define `JWT_SECRET_KEY`, `FRONTEND_MAGIC_LOGIN_URL`, and `POST_LOGIN_REDIRECT_URL`. For local-only tests
   you can keep the default SQLite `DATABASE_URL`, which FastAPI will create automatically.

3. Start the API:
   ```bash
   uvicorn backend.app:app --reload
   ```

The following routes are now available (they are the same whether you run locally or inside Docker):

- `POST /auth/magic-link/request` – issues a one-time magic link token and emails it to the user.
- `GET /auth/magic-login?token=<RAW_TOKEN>` – validates a magic link token and returns a signed JWT. Pass `response_mode=cookie` to set the JWT inside an `HttpOnly` cookie and redirect to the configured `POST_LOGIN_REDIRECT_URL`.
- `POST /webhooks/stripe` – consumes Stripe checkout events and grants `full_access` to matching users.

- `GET /catalog/free` – returns the entries listed in `audios-free.json` for everyone (no authentication required).
- `GET /catalog/premium` – returns the private entries stored in `backend/data/audios.json` for authenticated users with `full_access`.

All state is stored using SQLAlchemy models for `users` and `magic_link_tokens`, matching the schema from the documentation.

### Local end-to-end walkthrough

Follow these steps to see the full flow (database, email-free magic link, cookies, and catalog protection) from your browser:

1. **Backend configuration**
   - Keep `DATABASE_URL=sqlite:///./audiovook.db` for the quickest setup; the file is created the moment the API boots.
   - Set `FRONTEND_MAGIC_LOGIN_URL=http://localhost:8000/auth/magic-login` so emails point to your local API while testing.
   - Add `POST_LOGIN_REDIRECT_URL=http://localhost:6060/index.html?login=ok` so cookie responses send you back to the local catalog.
   - Leave the SMTP variables empty during development—the backend logs the magic link when email is disabled.

2. **Run the backend**

   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn backend.app:app --reload
   ```

   The first boot automatically creates the SQLite database and both tables.

3. **Create a subscriber account**

   ```bash
   python -m backend.manage create-user you@example.com --full-access
   ```

   Run `python -m backend.manage list-users` any time to inspect what is stored.

4. **Serve the frontend**

   From the repository root, start a static server so the browser can load `index.html` and the `AUDIOS/` assets:

   ```bash
   python -m http.server 6060
   ```

   The catalog and player automatically target `http://localhost:8000` for API calls when the page is served from `localhost`.

5. **Request and consume a magic link**
   - Visit <http://localhost:6060/index.html>, enter the email you created, and submit the form.
   - Because SMTP is disabled, the backend prints a log similar to: `Skipping email send...magic_link_login?...token=XYZ`.
   - Copy the URL, open it in the browser, and add `&response_mode=cookie` if you want an HttpOnly cookie plus redirect (the default redirect points to `POST_LOGIN_REDIRECT_URL`).

6. **Verify catalog protection**
   - Anonymous users (or fresh browsers) hit `/catalog/free` and see only the entries from `audios-free.json`.
   - After clicking the magic link, the cookie lets the frontend merge `/catalog/premium` with the open catalog, so premium stories appear.
   - The static fallback has been limited to `audios-free.json`, preventing the bundled premium catalog from leaking offline.

7. **Play audio locally**
   - The player automatically loads media from the same origin that served the HTML when it detects `localhost`, so hosting the repository via `python -m http.server 6060` also exposes the `AUDIOS/` directory for playback.

### Security hardening

- **Rate limiting**: `MAGIC_LINK_RATE_LIMIT_MAX_REQUESTS` and `MAGIC_LINK_RATE_LIMIT_WINDOW_MINUTES` prevent excessive link generation per email.
- **Suspicious login heuristics**: The backend compares both IP and user-agent deltas before blocking to avoid false positives, with optional strict IP enforcement.
- **Cookie-based login**: When `response_mode=cookie`, tokens are set inside an `HttpOnly` cookie (configurable name, domain, SameSite, and Secure flags) and the user is redirected only if the host is on the allow-list defined in `ALLOWED_REDIRECT_HOSTS`.
- **Localized HTML emails**: Every login email now contains Catalan and English content plus a styled HTML button.
- **CORS protection**: `ALLOWED_CORS_ORIGINS` limits which frontends can call the API with credentials. The default allow-list already covers localhost development and the production domain.

## Frontend login panel

`index.html` ships with a lightweight login panel where users can enter their email, submit the request, and see friendly status updates. The script automatically targets the backend hosted at `https://api.audiovook.com` in production (or `http://localhost:8000` for local development). To point to a different backend without rebuilding the page, set `window.__AUDIOVOOK_API__` before the script executes:

```html
<script>
  window.__AUDIOVOOK_API__ = "https://staging-api.audiovook.com";
</script>
```

After a successful cookie-based login the backend redirects back to `/?login=ok`, triggering a toast that confirms the session is ready.
