"""SQLite access helpers. Plain SQL keeps the code easy for a student team to read."""
import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "schema.sql")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_schema(path=None):
    path = path or current_app.config["DATABASE"]
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        con.executescript(fh.read())
    con.commit()
    con.close()


def query(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = get_db().execute(sql, args).fetchone()
    return dict(r) if r else None


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_app(app):
    app.teardown_appcontext(close_db)
