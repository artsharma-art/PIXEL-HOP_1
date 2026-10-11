import os
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import security

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("WARNING: SECRET_KEY not set; using a random key. Sessions reset on every restart.")

SESSION_TTL = int(os.getenv("SESSION_DAYS", "30")) * 86400
MAX_SCORE = int(os.getenv("MAX_SCORE", "5000"))
SECURE_COOKIE = bool(os.getenv("RENDER")) or os.getenv("COOKIE_SECURE") == "1"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
DUMMY_HASH = security.hash_password("not-a-real-password")

app = FastAPI(title="Pixel Hop API", version="1.0.0")
db.init()

_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, limit: int = 10, window: int = 300) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    if len(_hits) > 10000:
        _hits.clear()
    q = _hits[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again in a few minutes.")
    q.append(now)


def start_session(response: Response, user_id: int) -> None:
    response.set_cookie("session", security.make_token(user_id, SECRET_KEY, SESSION_TTL),
                        max_age=SESSION_TTL, httponly=True, samesite="lax", secure=SECURE_COOKIE, path="/")


def current_user(request: Request):
    uid = security.read_token(request.cookies.get("session"), SECRET_KEY)
    return db.get_user(uid) if uid else None


def require_user(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first.")
    return user


class Creds(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class ScoreIn(BaseModel):
    difficulty: int = Field(ge=0, le=2)
    score: int = Field(ge=0)


@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health():
    return {"ok": True, "service": "Pixel Hop"}


@app.post("/api/register")
def register(creds: Creds, request: Request, response: Response):
    rate_limit(request)
    username = creds.username.strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="Username must be 3-20 letters, numbers or underscores.")
    if not 8 <= len(creds.password) <= 128:
        raise HTTPException(status_code=400, detail="Password must be 8-128 characters.")
    user_id = db.create_user(username, security.hash_password(creds.password))
    if user_id is None:
        raise HTTPException(status_code=409, detail="That username is taken.")
    start_session(response, user_id)
    return {"username": username}


@app.post("/api/login")
def login(creds: Creds, request: Request, response: Response):
    rate_limit(request)
    user = db.get_user_by_name(creds.username.strip())
    if user is None:
        security.verify_password(creds.password, DUMMY_HASH)  # keep timing similar
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if not security.verify_password(creds.password, user["pw_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    start_session(response, user["id"])
    return {"username": user["username"]}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    user = current_user(request)
    return {"username": user["username"] if user else None}


@app.get("/api/scores/me")
def my_scores(request: Request):
    return db.user_scores(require_user(request)["id"])


@app.post("/api/scores")
def post_score(body: ScoreIn, request: Request):
    user = require_user(request)
    return db.submit_score(user["id"], body.difficulty, min(body.score, MAX_SCORE))


@app.get("/api/leaderboard")
def leaderboard():
    return db.leaderboard(10)


os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
