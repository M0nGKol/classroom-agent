# Per-user Google sign-in setup

This lets each visitor of the deployed app sign in with their **own** Google
account, so Calendar events and Gmail invitations are created/sent as them
(instead of the single account behind `backend/token.json`).

If a visitor doesn't sign in, "Run Now" still works exactly as before, using
the deployer's `token.json`/`credentials.json`.

---

## 1. Create a "Web application" OAuth client

This is **separate** from the existing "Desktop app" OAuth client used for
`credentials.json` — you'll end up with two OAuth clients in the same Google
Cloud project.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → your project (the one with the Calendar/Gmail APIs enabled).
2. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**.
3. Application type: **Web application**.
4. Name it something like "AI Classroom Agent (web)".
5. **Authorized JavaScript origins**: add your Vercel frontend URL, e.g.
   `https://classroom-agent.vercel.app`
6. **Authorized redirect URIs**: add your Render backend URL + `/api/auth/google/callback`, e.g.
   `https://ai-classroom-agent.onrender.com/api/auth/google/callback`
7. Create. Copy the **Client ID** and **Client secret**.

---

## 2. Add test users (required while the app is in "Testing")

The Calendar/Gmail scopes are "sensitive", so unless you've published and
verified the app, only **test users** you explicitly list can sign in.

1. **APIs & Services → OAuth consent screen**.
2. Make sure these scopes are listed under "Data access":
   - `.../auth/calendar.events`
   - `.../auth/gmail.send`
   - `.../auth/userinfo.email`
   - `openid`
3. Under **Audience → Test users**, click **Add users** and add the Gmail
   address of every tester (up to 100). Each tester must use one of these
   addresses to sign in.

---

## 3. Add environment variables on Render

In your Render service → **Environment**, add:

| Key | Value |
|---|---|
| `GOOGLE_CLIENT_ID` | from step 1 |
| `GOOGLE_CLIENT_SECRET` | from step 1 |
| `GOOGLE_REDIRECT_URI` | `https://<your-render-url>/api/auth/google/callback` |
| `SESSION_SECRET` | any long random string, e.g. output of `openssl rand -hex 32` |

`FRONTEND_URL` should already be set (from the main deploy) — it's reused
here to redirect users back to the frontend after sign-in.

Redeploy/restart the Render service so the new env vars take effect.

---

## 4. Try it

1. Open your Vercel app. You should see a **"Sign in with Google"** card
   above the upload area (it only appears once `GOOGLE_CLIENT_ID` etc. are
   set on the backend).
2. Click **Sign in** → choose a test-user account → grant Calendar + Gmail
   access.
3. You'll be redirected back to the app, now showing your email as signed in.
4. Run the automation — events/emails will go through that Google account.

---

## Notes

- Each tester's sign-in is stored in their browser's session cookie (not on
  disk), so testers never see or need your `credentials.json`/`token.json`.
- Scheduled/auto runs (the daily scheduler, file-watcher, "Trigger Now") have
  no associated user and always use the deployer's `token.json`.
- If `GOOGLE_CLIENT_ID`/`SECRET`/`GOOGLE_REDIRECT_URI` aren't set, the sign-in
  card is hidden and everything behaves exactly as before.
