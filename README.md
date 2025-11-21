# avook-dual

Audiovook Dual now ships with a FastAPI backend that implements the secure magic-link flow described in `docs/magic_link_flow.md`.

## Docker quickstart

1. Copy the backend environment template and set at least `JWT_SECRET_KEY` plus the frontend URLs you want to use. The template
   already targets a fully local stack (`FRONTEND_MAGIC_LOGIN_URL=http://localhost:6060/auth/magic-login` and
   `POST_LOGIN_REDIRECT_URL=http://localhost:6060/?login=ok`), so you can keep those defaults while developing. Set
   `EMAIL_ENABLED=false` (or leave the SMTP fields empty) for local testing—the API logs the magic link URL whenever email
   delivery is disabled. When deploying to production, override the URLs with your public domain.

   ```bash
   cp backend/.env.example backend/.env
   ```

2. (Optional) Copy the root Compose overrides whenever you want to change the published host ports. By default the backend binds
   to `http://localhost:8000` and the frontend to `http://localhost:6060`. If those numbers are already taken on your machine,
   set new values inside `.env` before running Docker Compose.

   ```bash
   cp .env.example .env
   # edit BACKEND_PORT / FRONTEND_PORT when you need different host ports
   ```

3. Build and start both the FastAPI backend and the static frontend:

   ```bash
   docker compose up --build
   ```

   Once the containers finish booting you should be able to open `http://localhost:6060` (frontend) and `http://localhost:8000/docs`
   (FastAPI docs). If you customized the ports via `.env`, substitute those values in your browser URLs.

   The compose file automatically points the backend to a SQLite database stored in the named volume `backend-data`. The file is
   created the first time the container boots, so you do not need to provision anything manually.

4. Create or inspect subscribers directly inside the running image:

   ```bash
   docker compose run --rm backend python -m backend.manage create-user you@example.com --full-access
   docker compose run --rm backend python -m backend.manage list-users
   ```

   After requesting a magic link from the browser you will see the login URL printed in the backend logs. Copy it into the
   browser, or paste the raw token after `http://localhost:6060/auth/magic-login?token=` and the helper page will exchange the
   token for you. The backend automatically appends `redirect=<POST_LOGIN_REDIRECT_URL>` to every link, so the helper (JSON mode)
   and the backend (cookie mode) always land on the same destination. Append `&response_mode=cookie` only if you hit the backend
   URL directly and want to force the HttpOnly cookie redirect yourself. If you accidentally open the helper over
   `https://localhost`, it automatically downgrades back to `http://localhost` while preserving the original port so
   mixed-content restrictions never block the redirect to the FastAPI server on port 8000.

Stop everything at any time with `docker compose down` (add `-v` if you also want to delete the SQLite volume).

### Monitoring Docker logs and ports

Use the following commands whenever you need to troubleshoot container startup or watch the magic-link URLs that the backend logs
while SMTP is disabled:

```bash
# See a live log stream for the API (press Ctrl+C to stop following)
docker compose logs -f backend

# Print the latest frontend log output
docker compose logs frontend

# Confirm which ports are bound if you customized them in .env
docker compose ps
docker compose port backend 8000
docker compose port frontend 80
```

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

   At minimum you must define `JWT_SECRET_KEY`, `FRONTEND_MAGIC_LOGIN_URL`, and `POST_LOGIN_REDIRECT_URL`. The template now uses
   a SQLite `DATABASE_URL=sqlite:///./audiovook.db` plus localhost URLs so you can boot the API without editing anything else.
   FastAPI creates the SQLite database automatically inside the `backend/` folder. Override the URLs when deploying to a public
   host. Set `PAYPAL_IPN_VERIFY_URL=https://ipnpb.sandbox.paypal.com/cgi-bin/webscr` when you want to validate IPN messages
   against the PayPal sandbox instead of production. Hosted PayPal button IDs live in `catalog/packages.json` and are rendered
   directly on `products.html`.

   > **Note:** List-style settings such as `ALLOWED_REDIRECT_HOSTS` and `ALLOWED_CORS_ORIGINS` accept either comma-separated
   > values or JSON arrays. Leave the variables blank if you prefer to fall back to the built-in defaults.

3. Start the API:

   ```bash
   uvicorn backend.app:app --reload
   ```

### Catalog data layout

- `catalog/titles.json` stores the authoritative metadata for every title (description, asset names, cover, etc.).
- `catalog/packages.json` groups `title_ids` into sellable packages. One of the packages must have `"is_free": true` so the backend knows which entries are public. Paid packages now include optional PayPal hosted button identifiers to render the checkout buttons.
- `audios-free.json` remains as a static fallback for browsers that cannot reach the API (for example when running `python -m http.server` without the backend). The file mirrors the titles listed in the free package.

### API overview

The following routes are now available (they are the same whether you run locally or inside Docker):

- `POST /auth/magic-link/request` – issues a one-time magic link token and emails it to the user.
- `GET /auth/magic-login?token=<RAW_TOKEN>` – validates a magic link token and returns a signed JWT. Pass `response_mode=cookie` to set the JWT inside an `HttpOnly` cookie and redirect to the configured `POST_LOGIN_REDIRECT_URL`.
- `POST /webhooks/paypal` – consumes PayPal IPN notifications and grants the matching catalog packages to the purchaser.

- `GET /catalog/free` – returns the entries assigned to the `is_free` package inside `catalog/packages.json`.
- `GET /catalog/packages/{package_id}` – returns a single package for authenticated users who own it (or have `full_access`).
- `GET /auth/me` – returns the authenticated user profile, including the list of package IDs that have been granted.

PayPal IPN posts are validated against the configured verification URL (`PAYPAL_IPN_VERIFY_URL`) and map the `custom` field back to package IDs from `catalog/packages.json`.

All state is stored using SQLAlchemy models for `users` and `magic_link_tokens`, matching the schema from the documentation.

### Local end-to-end walkthrough (without Docker)

Follow these steps to see the full flow (database, email-free magic link, cookies, and catalog protection) from your browser:

1. **Backend configuration**
   - Keep `DATABASE_URL=sqlite:///./audiovook.db` for the quickest setup; the file is created the moment the API boots.
   - The `.env.example` already points `FRONTEND_MAGIC_LOGIN_URL` to `http://localhost:6060/auth/magic-login`, which is exactly
     where the static frontend runs when you follow the instructions above. Adjust the value whenever you expose the helper page
     on a different host.
   - Update `POST_LOGIN_REDIRECT_URL` if you need a different frontend origin (for example,
     `http://localhost:6060/index.html?login=ok` when serving the static site from the repo root).
   - Cookie responses automatically drop the `Secure` flag on plain `http://` origins so local testing works out of the box. If
     you prefer to harden the behavior, set `AUTH_COOKIE_SECURE=false` explicitly in `.env` to mirror production defaults.
   - Either set `EMAIL_ENABLED=false` or leave the SMTP variables empty during development—the backend logs the magic link when
     email is disabled or fails.

2. **Run the backend**

   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn backend.app:app --reload
   ```

   The first boot automatically creates the SQLite database and both tables.

3. **Create a subscriber account**

   ```bash
   python -m backend.manage create-user you@example.com --package pkg-a1
   ```

   Add `--full-access` if you want to bypass per-package entitlements and unlock every package for that user.

   Run `python -m backend.manage list-users` any time to inspect what is stored.

   > **Docker users:** execute the same management commands inside the running
   > container, for example:
   >
   > ```bash
   > docker compose exec backend python -m backend.manage create-user you@example.com --package pkg-a1
   > docker compose exec backend python -m backend.manage list-users
   > ```

4. **Serve the frontend**

   From the repository root, start a static server so the browser can load `index.html` and the `AUDIOS/` assets (skip this if
   you already started the frontend container):

   ```bash
   python -m http.server 6060
   ```

   The catalog and player automatically target `http://localhost:8000` for API calls when the page is served from `localhost`.

5. **Request and consume a magic link**
   - Visit <http://localhost:6060/index.html>, enter the email you created, and submit the form.
   - Because SMTP is disabled, the backend prints a log similar to:
     `Magic link URL for you@example.com (token=XYZ): http://localhost:6060/auth/magic-login?token=XYZ — EMAIL_ENABLED is false`.
  - Copy the URL, then either open it directly (adding `&response_mode=cookie` to trigger an HttpOnly cookie) **or** paste the raw token into `http://localhost:6060/auth/magic-login?token=<TOKEN>` so the frontend helper page redeems it for you. Every link now carries `redirect=<POST_LOGIN_REDIRECT_URL>`, so whichever destination you configure in `.env` is reused by the helper without extra tweaks.
  - When the helper detects it is running over plain `http://localhost`, it automatically switches to JSON mode, stores the JWT inside `localStorage`, and then sends you back to the catalog. Both `index.html` and `player.html` now attach that token as a `Bearer` header when calling `/auth/me` and `/catalog/packages/<package_id>`, so you can test premium access without tweaking cookie settings.
  - If your browser enforces “HTTPS-only” mode, add an exception for `http://localhost:6060` (or use `http://127.0.0.1:6060`) because the helper needs plain HTTP to talk to the FastAPI container; it already tries to downgrade `https://localhost` links while preserving port `:6060`.

6. **Verify catalog protection**
   - Anonymous users (or fresh browsers) hit `/catalog/free` and see only the entries from `audios-free.json`.
   - After clicking the magic link, the frontend calls `/auth/me` to read the package IDs granted to the account and then loads `/catalog/packages/<package_id>` for each one, so premium stories appear.
   - The static fallback has been limited to `audios-free.json`, preventing the bundled premium catalog from leaking offline.

7. **Play audio locally**
   - The player automatically loads media from the same origin that served the HTML when it detects `localhost`, so hosting the repository via `python -m http.server 6060` also exposes the `AUDIOS/` directory for playback.

### Email delivery & troubleshooting

- **Emails while developing**: Set `EMAIL_ENABLED=false` or leave `SMTP_HOST` empty and the backend will log a fully qualified
  magic link (email, token, and URL). When SMTP is enabled but a send fails, the backend logs the same information plus the
  error reason, so you can always copy the login URL during development.
- **Database creation**: Both the manual and Docker workflows run `Base.metadata.create_all` during startup. When you use SQLite
  the file is created automatically; with Postgres the tables are created inside the configured database.
- **Premium catalog locked down**: Anonymous browsers only fetch `/catalog/free`, which mirrors `audios-free.json`. Authenticated
  sessions use `/auth/me` + `/catalog/packages/{package_id}` with their JWT or HttpOnly cookie, so paid stories remain protected.

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

If you want to close the session, use the **Tancar sessió** button in the header. It clears the browser tokens and calls `POST /auth/logout` to expire the HttpOnly cookie before reloading the page.
