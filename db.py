import os
import sqlite3
import time
from typing import Optional

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pixelhop.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init() -> None:
    with _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              pw_hash TEXT NOT NULL,
              created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS scores(
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              diff INTEGER NOT NULL CHECK(diff BETWEEN 0 AND 2),
              score INTEGER NOT NULL,
              updated INTEGER NOT NULL,
              PRIMARY KEY(user_id, diff));
            """
        )


def create_user(username: str, pw_hash: str) -> Optional[int]:
    try:
        with _conn() as c:
            cur = c.execute("INSERT INTO users(username,pw_hash,created) VALUES(?,?,?)",
                            (username, pw_hash, int(time.time())))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_name(username: str) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def user_scores(user_id: int) -> dict:
    out = {"b0": 0, "b1": 0, "b2": 0}
    with _conn() as c:
        for r in c.execute("SELECT diff,score FROM scores WHERE user_id=?", (user_id,)):
            out[f"b{r['diff']}"] = r["score"]
    return out


def submit_score(user_id: int, diff: int, score: int) -> dict:
    with _conn() as c:
        c.execute(
            """INSERT INTO scores(user_id,diff,score,updated) VALUES(?,?,?,?)
               ON CONFLICT(user_id,diff) DO UPDATE SET
                 updated=CASE WHEN excluded.score>score THEN excluded.updated ELSE updated END,
                 score=MAX(score,excluded.score)""",
            (user_id, diff, score, int(time.time())),
        )
    return user_scores(user_id)


def leaderboard(limit: int = 10) -> list:
    with _conn() as c:
        rows = c.execute(
            """SELECT u.username,
                      SUM(CASE WHEN s.diff=0 THEN s.score ELSE 0 END) AS b0,
                      SUM(CASE WHEN s.diff=1 THEN s.score ELSE 0 END) AS b1,
                      SUM(CASE WHEN s.diff=2 THEN s.score ELSE 0 END) AS b2,
                      SUM(s.score) AS tot
               FROM scores s JOIN users u ON u.id=s.user_id
               GROUP BY u.id ORDER BY tot DESC, u.username LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]
