"""Queries over the Elo rating tables."""
from app.db import query


def rankings(limit=50, min_matches=100):
    """Current world ranking by Elo rating."""
    rows = query("""
        SELECT t.name AS team, e.rating, e.matches, e.peak_rating, e.peak_date
        FROM elo_ratings e JOIN teams t ON t.id = e.team_id
        WHERE e.matches >= ?
        ORDER BY e.rating DESC LIMIT ?""", (min_matches, limit))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["rating"] = round(r["rating"], 1)
        r["peak_rating"] = round(r["peak_rating"], 1)
    return rows


def rating_series(team, every=5):
    """A team's rating over time, thinned out so charts stay responsive."""
    rows = query("""
        SELECT h.date, h.rating FROM elo_history h
        JOIN teams t ON t.id = h.team_id
        WHERE t.name = ? ORDER BY h.date""", (team,))
    if len(rows) > 400:
        rows = rows[::every] + rows[-1:]
    return rows


def calibration_table():
    """The measured draw rate per Elo-gap bucket (shown on the model page)."""
    return query("""SELECT bucket, gap_lo, gap_hi, matches, draws, draw_rate
                    FROM draw_calibration ORDER BY bucket""")
