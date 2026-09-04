"""Match outcome predictor built on top of the Elo ratings.

Elo alone gives one number: the expected score `E` (a win counts 1, a draw 0.5).
To turn that into three probabilities we need to know how often draws happen,
so the draw model is *calibrated on the real match history*:

    for every historical match we know the Elo gap before kick-off, so we bucket
    150 years of matches by that gap and measure the actual draw rate in each
    bucket.

Then, since E = P(win) + 0.5 * P(draw):

    P(draw) = calibrated draw rate for this Elo gap
    P(home) = E - P(draw) / 2
    P(away) = 1 - P(home) - P(draw)
"""
from app.config import ELO_HOME_ADVANTAGE
from app.db import query
from app.services.elo import expected_score

BUCKET_SIZE = 50   # Elo points per calibration bucket


def bucket_for(diff):
    """Which calibration bucket an Elo gap falls into."""
    return int(abs(diff) // BUCKET_SIZE)


def load_calibration():
    """Draw rate per Elo-gap bucket, as measured from the historical data."""
    rows = query("SELECT bucket, matches, draw_rate FROM draw_calibration ORDER BY bucket")
    return {r["bucket"]: r["draw_rate"] for r in rows}


def draw_probability(diff, calibration):
    """Look up the empirical draw rate, falling back to the nearest bucket."""
    if not calibration:
        return 0.25
    b = bucket_for(diff)
    if b in calibration:
        return calibration[b]
    return calibration[max(calibration)]


def probabilities(rating_home, rating_away, calibration, neutral=True):
    """The three outcome probabilities for one fixture."""
    advantage = 0.0 if neutral else ELO_HOME_ADVANTAGE
    expected = expected_score(rating_home, rating_away, advantage)
    diff = (rating_home + advantage) - rating_away

    p_draw = draw_probability(diff, calibration)
    p_home = expected - p_draw / 2
    p_away = 1 - p_home - p_draw

    # Clamp then renormalise so we always return a valid distribution.
    p_home, p_draw, p_away = (max(0.0, p) for p in (p_home, p_draw, p_away))
    total = p_home + p_draw + p_away or 1.0
    return p_home / total, p_draw / total, p_away / total


def team_rating(name):
    row = query("""SELECT e.rating, e.matches FROM elo_ratings e
                   JOIN teams t ON t.id = e.team_id WHERE t.name = ?""", (name,), one=True)
    return row


def predict(team_a, team_b, neutral=True):
    """Public entry point used by the API and the web form."""
    ra, rb = team_rating(team_a), team_rating(team_b)
    if not ra or not rb:
        return None
    calibration = load_calibration()
    p_a, p_draw, p_b = probabilities(ra["rating"], rb["rating"], calibration, neutral)
    return {
        "team_a": team_a, "team_b": team_b, "neutral": neutral,
        "rating_a": round(ra["rating"], 1), "rating_b": round(rb["rating"], 1),
        "rating_gap": round(ra["rating"] - rb["rating"], 1),
        "p_a": round(p_a, 4), "p_draw": round(p_draw, 4), "p_b": round(p_b, 4),
        "pct_a": round(100 * p_a, 1), "pct_draw": round(100 * p_draw, 1),
        "pct_b": round(100 * p_b, 1),
        "favourite": team_a if p_a > p_b else team_b if p_b > p_a else "Even",
    }


def metrics():
    """How good is the model? Read back the scores measured during the ETL."""
    return {r["name"]: r["value"] for r in query("SELECT name, value FROM model_metrics")}
