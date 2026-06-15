# Deploying: backend on Render, frontend on Vercel

## 0. Push to GitHub
Both Render and Vercel deploy from a Git repo. Push this project (with `backend/` and `frontend/` folders) to GitHub first.

**Do not commit secrets.** Make sure these stay out of git (add to `.gitignore` if not already):
- `backend/.env`
- `backend/credentials.json`
- `backend/token.json`
- `backend/client_secret_*.json`

---

## 1. Backend on Render

1. Go to render.com → **New → Web Service** → connect your GitHub repo.
2. **Root Directory**: `backend`
3. **Runtime**: Python 3
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   (Render sets `$PORT` automatically — don't hardcode 8000.)
6. **Environment variables** (Settings → Environment), copy from your local `backend/.env`:
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL`
   - `ZOOM_ACCOUNT_ID`
   - `ZOOM_CLIENT_ID`
   - `ZOOM_CLIENT_SECRET`
   - `ZOOM_HOST_EMAIL`
   - `SKIP_EXTERNAL_APIS` / `SKIP_GEMINI` (only if you want to keep them)
   - `FRONTEND_URL` — set this once you have your Vercel URL, e.g. `https://your-app.vercel.app` (CORS in `app.py` now reads this; comma-separate multiple values in `FRONTEND_URLS` for preview deploys)
7. **Google credentials (Gmail/Calendar)**: `calendar_client.py` and `gmail_client.py` need `credentials.json` and `token.json` next to them in `backend/`. Since `run_local_server()` OAuth can't run on Render (no browser), generate `token.json` locally first (run the app once locally so it completes the OAuth flow), then upload both files to Render as **Secret Files** (Settings → Secret Files), with paths `backend/credentials.json` and `backend/token.json`. As long as the refresh token is valid, it'll refresh silently on the server.
8. Deploy. Note the resulting URL, e.g. `https://ai-classroom-agent.onrender.com`.

Free tier note: Render free web services spin down when idle and take ~30–60s to wake on the next request.

---

## 2. Frontend on Vercel

1. Go to vercel.com → **Add New → Project** → import the same GitHub repo.
2. **Root Directory**: `frontend`
3. Framework preset: Next.js (auto-detected).
4. **Environment variable**:
   - `NEXT_PUBLIC_API_URL` = your Render backend URL (e.g. `https://ai-classroom-agent.onrender.com`) — no trailing slash.
   - Add it for Production (and Preview if you want preview deploys to hit the same backend).
5. Deploy. Note the resulting URL, e.g. `https://ai-classroom-agent.vercel.app`.

---

## 3. Connect them

1. Back in Render, set `FRONTEND_URL` to your Vercel URL from step 2, and redeploy (or it picks it up on next deploy/restart) so CORS allows requests from the frontend.
2. Open the Vercel URL and confirm the app can reach `/api/health` on the Render backend (check browser console/network tab for CORS or connection errors).

---

## Optional: let testers sign in with their own Google account

See `GOOGLE_OAUTH_SETUP.md` for adding per-user "Sign in with Google" (so
Calendar events/emails go through each tester's own account). Requires a few
extra env vars (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_REDIRECT_URI`, `SESSION_SECRET`) — everything works without it too.

---

## What was changed in the code to support this

- `frontend/app/page.tsx`, `run/page.tsx`, `report/page.tsx`: `API_BASE` now reads `process.env.NEXT_PUBLIC_API_URL`, falling back to `http://localhost:8000` for local dev.
- `backend/app.py`: CORS `allow_origins` now also includes `FRONTEND_URL` / `FRONTEND_URLS` from environment variables, in addition to localhost.
- Added per-user Google sign-in (session cookies + `/api/auth/*` endpoints) — see `GOOGLE_OAUTH_SETUP.md`.
