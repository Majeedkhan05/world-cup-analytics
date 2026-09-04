"""Elo rating engine for international football teams.

The whole model is three short formulas:

  1. Expectation   E_home = 1 / (1 + 10 ** (-(R_home + H - R_away) / 400))
  2. Margin factor M      = sqrt(max(1, goal_difference))   -> big wins count more
  3. Update        R'     = R + K * weight * M * (S - E)    where S = 1/0.5/0

`S` is the actual result (win/draw/loss) and `E` is what the ratings expected.
A team only gains points when it does better than its rating predicted.

Everything here is pure Python on plain dicts, which keeps it unit-testable
without a database.
"""
import math
from app.config import (
    ELO_START, ELO_HOME_ADVANTAGE, ELO_K_BASE, ELO_WEIGHTS, ELO_WEIGHT_DEFAULT,
    ELO_MARGIN_CAP,
)


def expected_score(rating_a, rating_b, home_advantage=0.0):
    """Probability that A beats B, on the classic 400-point logistic curve."""
    diff = (rating_a + home_advantage) - rating_b
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def margin_factor(home_score, away_score, cap=None):
    """Weight a result by how emphatic it was: 1-0 -> 1.0, 4-0 -> 2.0.

    Capped, because a 9-0 rout says little more about a team's strength than a
    5-0 one and would otherwise swing the rating wildly.
    """
    cap = ELO_MARGIN_CAP if cap is None else cap
    return min(cap, math.sqrt(max(1, abs(home_score - away_score))))


def outcome(home_score, away_score):
    """Actual score from the home team's perspective: 1 win, 0.5 draw, 0 loss."""
    if home_score > away_score:
        return 1.0
    if home_score < away_score:
        return 0.0
    return 0.5


def tournament_weight(tournament):
    """A World Cup match matters more than a friendly."""
    return ELO_WEIGHTS.get(tournament, ELO_WEIGHT_DEFAULT)


def update_pair(rating_home, rating_away, home_score, away_score,
                tournament="Friendly", neutral=False):
    """Return the pair of new ratings after one match.

    Elo is zero-sum: whatever the home side gains, the away side loses.
    """
    advantage = 0.0 if neutral else ELO_HOME_ADVANTAGE
    expected = expected_score(rating_home, rating_away, advantage)
    actual = outcome(home_score, away_score)
    k = ELO_K_BASE * tournament_weight(tournament) * margin_factor(home_score, away_score)
    delta = k * (actual - expected)
    return rating_home + delta, rating_away - delta


class EloEngine:
    """Replays a chronological match history and tracks every team's rating."""

    def __init__(self, start=ELO_START):
        self.start = start
        self.ratings = {}       # team -> current rating
        self.played = {}        # team -> matches played
        self.peak = {}          # team -> (peak rating, date it was set)
        self.history = []       # (team, date, rating) after each match
        self.pre_match = {}     # match id -> (home rating, away rating) BEFORE it

    def rating(self, team):
        return self.ratings.get(team, self.start)

    def process(self, match):
        """Apply one match. `match` is a dict/Row with the usual columns.

        Returns the two ratings as they stood *before* the match, which is what
        a fair prediction has to be based on.
        """
        home, away = match["home_team"], match["away_team"]
        pre_home, pre_away = self.rating(home), self.rating(away)
        if "id" in match:
            self.pre_match[match["id"]] = (pre_home, pre_away)
        new_home, new_away = update_pair(
            pre_home, pre_away,
            match["home_score"], match["away_score"],
            match.get("tournament", "Friendly"),
            bool(match.get("neutral", False)),
        )
        for team, rating in ((home, new_home), (away, new_away)):
            self.ratings[team] = rating
            self.played[team] = self.played.get(team, 0) + 1
            best, _ = self.peak.get(team, (float("-inf"), None))
            if rating > best:
                self.peak[team] = (rating, match["date"])
            self.history.append((team, match["date"], rating))
        return pre_home, pre_away

    def run(self, matches):
        """Process an iterable of matches assumed to be in date order."""
        for m in matches:
            self.process(m)
        return self

    def table(self, min_matches=30):
        """Current rankings, strongest first."""
        rows = []
        for team, rating in self.ratings.items():
            if self.played[team] < min_matches:
                continue
            peak_rating, peak_date = self.peak[team]
            rows.append({
                "team": team,
                "rating": round(rating, 1),
                "matches": self.played[team],
                "peak_rating": round(peak_rating, 1),
                "peak_date": peak_date,
            })
        rows.sort(key=lambda r: -r["rating"])
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows
