"""Thin SQLite access layer.

Deliberately no ORM: every query in this project is plain SQL, so the data
access story is easy to read and easy to explain.
"""
import sqlite3
from flask import g, current_app
from app.config import DB_PATH


def connect(path=DB_PATH):
    """Open a connection that returns dict-like rows and enforces FKs."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Per-request connection, cached on Flask's application context."""
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    """Run a SELECT and return list[dict] (or a single dict when one=True)."""
    rows = get_db().execute(sql, params).fetchall()
    rows = [dict(r) for r in rows]
    if one:
        return rows[0] if rows else None
    return rows
