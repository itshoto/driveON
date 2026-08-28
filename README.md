# driveON

One driveON account. Up to 5 connected Google Drive accounts. One unified storage system.

This is a from-scratch build following the driveON SOP: **Phase 1** (auth, Google OAuth
connect, 5-account limit, duplicate-account prevention, storage dashboard) and **Phase 2**
(normal upload/download/delete/rename, unified file browser) are implemented. Distributed
chunked storage (Phase 3) and the AI PDF assistant (Phase 4) are not built yet.

## Stack

| Layer          | Technology                                |
| -------------- | ------------------------------------------ |
| Frontend       | Next.js 14 (App Router) + Tailwind CSS      |
| Auth           | Firebase Authentication                     |
| Backend        | Django 5 + Django REST Framework            |
| Database       | PostgreSQL                                  |
| Background jobs| Celery + Redis (wired, not yet used by Phase 1-2 flows) |
| Storage        | Google Drive API v3 (OAuth 2.0, per-user)   |

## Repository layout

```
driveon/
├── backend/            Django REST API
│   ├── config/          settings, urls, celery app
│   ├── users/           Firebase-verified auth, driveON profile, Plan
│   ├── google_accounts/ Google OAuth flow, encrypted token storage, Drive API client
│   ├── storage/         cross-account storage summary + allocation
│   └── files/           unified file browser, upload/download/delete/rename
└── frontend/            Next.js app (landing, auth, dashboard, drives, files)
```

## How auth works

Firebase Authentication owns credentials (email/password). The Django backend never sees a
password — it verifies the Firebase ID token on every request (`users/authentication.py`) and
maps it to a local `User` row keyed by `firebase_uid`. On first sign-up, the frontend calls
`POST /api/auth/sync` with a chosen `username`, which creates that row (this is where the
`UNIQUE(username)` / `UNIQUE(email)` constraints from the SOP are enforced). Subsequent logins
call the same endpoint idempotently.

## How Google Drive connection works

1. Frontend calls `GET /api/google/connect` (authenticated) → gets a Google consent URL.
2. Google redirects the browser to `GET /api/google/callback` with `code` + a signed `state`
   (no auth header reaches this endpoint, so the driveON user is recovered from `state`).
3. The backend exchanges the code for tokens, resolves the account's stable Google id (`sub`
   claim), and enforces two rules **server-side**, never trusting the frontend:
   - `UNIQUE(google_account_id)` — one Google account can only ever belong to one driveON user.
   - the plan's `max_google_accounts` (default 5) — checked against currently-connected accounts.
4. Tokens are encrypted (Fernet) before they ever touch PostgreSQL and are never sent to the
   frontend.

Removing an account doesn't delete the user's Drive files. If files depend on that account, the
first `DELETE` call returns `409` with a warning; the frontend shows "Remove anyway" which
retries with `?force=true`.

## How file upload/download works (Phase 2, non-chunked)

- Upload: the file's SHA-256 is computed from the spooled temp file, `storage.allocator` picks
  the connected account with the least free space that can still fit the whole file (best-fit,
  after refreshing live Drive quota), then it's pushed to Drive via a resumable upload.
- Download: streamed back from Drive via `StreamingHttpResponse` — the file is never buffered
  whole in server memory in either direction.
- If a file's account gets disconnected, the file flips to `partially_available` and download
  returns a `409` with an explanation instead of failing silently.

## Local setup

### 1. Postgres + Redis

Easiest via Docker: `docker compose up postgres redis -d` (see `docker-compose.yml`), or install
both locally and update `backend/.env` accordingly.

### 2. Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then fill in the values below
python manage.py migrate
python manage.py createsuperuser  # optional, for /admin
python manage.py runserver
```

Fill in `backend/.env`:

- `TOKEN_ENCRYPTION_KEY` — generate with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `FIREBASE_CREDENTIALS_PATH` — a Firebase service account JSON (Firebase Console → Project
  Settings → Service Accounts → Generate new private key)
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — a **Web application** OAuth client
  from Google Cloud Console → APIs & Services → Credentials, with
  `http://localhost:8000/api/google/callback` added as an authorized redirect URI, and the
  Google Drive API enabled on the project.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in your Firebase web app config
npm run dev
```

`NEXT_PUBLIC_FIREBASE_*` values come from Firebase Console → Project Settings → General → Your
apps → SDK setup and config (the same Firebase project as the backend's service account, with
Email/Password sign-in enabled under Authentication → Sign-in method).

Visit `http://localhost:3000`.

## Notable scope cuts (documented, not accidental)

- Chunked/distributed storage (splitting one file across multiple accounts) is Phase 3 and not
  implemented — `storage.allocator.select_account_for_file` currently requires one account with
  enough free space for the whole file.
- Streaming download doesn't re-verify the reconstructed file's checksum against the stored one
  (would require buffering to hash before streaming to the client, which defeats the point);
  the checksum is stored for future chunked-download reconstruction and dedup use.
- Drive quota sync is on-demand (checked when connecting and before each upload), not on a
  periodic Celery schedule yet, though Celery/Redis are wired up for Phase 3.
