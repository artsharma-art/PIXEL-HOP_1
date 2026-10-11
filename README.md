# Pixel Hop – website + login backend

A FastAPI backend (username/password accounts, saved scores, leaderboard) that also serves the Pixel Hop website, so you deploy one service.

## What's included
- Sign up / log in / log out with passwords hashed using scrypt
- Signed, HTTP-only session cookie (30 days)
- Best score per difficulty saved to your account; top-10 leaderboard
- Login rate limiting (10 attempts per 5 minutes per IP)
- SQLite database (no external services needed)

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# open http://localhost:8000
```

## Deploy: GitHub + Render
1. Create an empty GitHub repo and push everything in this folder (files at the repo root, `static/index.html` inside `static/`):
   ```bash
   git init && git add . && git commit -m "Pixel Hop"
   git branch -M main
   git remote add origin https://github.com/<you>/pixel-hop.git
   git push -u origin main
   ```
2. In Render: **New + → Blueprint**, pick the repo, **Apply**. (Or **New + → Web Service**, language **Docker**, health check path `/api/health`, and add an env var `SECRET_KEY` set to a long random string.)
3. Open your Render URL, go to the **Account** tab, and sign up.

## Important: keeping the data
SQLite lives on the server's disk. On Render's **free** plan the disk is wiped on every restart or redeploy, so accounts and scores will disappear. To keep them, use a paid instance with a persistent disk (see the commented block in `render.yaml`) and set `DB_PATH=/var/data/pixelhop.db`. For many users, move to PostgreSQL.

## Settings (environment variables)
`SECRET_KEY` (required in production), `DB_PATH`, `SESSION_DAYS` (30), `MAX_SCORE` (5000), `COOKIE_SECURE` (1 to force secure cookies; automatic on Render).

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/register` | `{"username","password"}` – create account and log in |
| POST | `/api/login` | log in |
| POST | `/api/logout` | log out |
| GET | `/api/me` | current username or null |
| GET/POST | `/api/scores/me`, `/api/scores` | read / submit best score `{"difficulty":0-2,"score":n}` |
| GET | `/api/leaderboard` | top 10 |

## Honest limitations
- Scores are reported by the browser, so a determined player can fake them. `MAX_SCORE` caps the damage; real cheat-proofing would need the game logic to run on the server.
- No password reset or email verification yet.
