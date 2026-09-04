"""Tests for the ETL transforms - the part most likely to silently corrupt data."""
import pandas as pd
import pytest

from app import etl


class TestCleanMatches:
    def _raw(self, rows):
        return pd.DataFrame(rows, columns=[
            "date", "home_team", "away_team", "home_score", "away_score",
            "tournament", "city", "country", "neutral"])

    def test_derives_year_and_world_cup_flag(self):
        df = etl.clean_matches(self._raw([
            ("1930-07-13", "France", "Mexico", 4, 1, "FIFA World Cup", "Montevideo", "Uruguay", "TRUE"),
            ("2001-01-01", "A", "B", 1, 1, "Friendly", "X", "Y", "FALSE"),
        ]))
        assert list(df["year"]) == [1930, 2001]
        assert list(df["is_world_cup"]) == [1, 0]
        assert list(df["neutral"]) == [1, 0]

    def test_drops_fixtures_that_were_never_played(self):
        df = etl.clean_matches(self._raw([
            ("2030-01-01", "A", "B", None, None, "Friendly", "X", "Y", "FALSE"),
            ("2001-01-01", "A", "B", 1, 0, "Friendly", "X", "Y", "FALSE"),
        ]))
        assert len(df) == 1

    def test_sorts_chronologically_and_assigns_ids(self):
        df = etl.clean_matches(self._raw([
            ("2005-01-01", "A", "B", 1, 0, "Friendly", "X", "Y", "FALSE"),
            ("1999-01-01", "C", "D", 2, 2, "Friendly", "X", "Y", "FALSE"),
        ]))
        assert list(df["date"]) == ["1999-01-01", "2005-01-01"]
        assert list(df["id"]) == [1, 2]


class TestBuildTeams:
    def test_every_team_gets_exactly_one_id(self):
        df = pd.DataFrame({"home_team": ["A", "B", "A"], "away_team": ["B", "C", "C"]})
        ids = etl.build_teams(df)
        assert sorted(ids) == ["A", "B", "C"]
        assert len(set(ids.values())) == 3


class TestPickFinal:
    def test_picks_the_last_match_when_there_is_a_real_final(self, sample_matches):
        df = sample_matches[sample_matches.date != "1950-07-16"].copy()
        final = etl.pick_final(df)
        assert final["date"] == "1950-07-09"

    def test_round_robin_tie_is_broken_by_team_strength(self, sample_matches):
        # Two matches share the last date; the decisive one is Uruguay v Brazil,
        # because those two are the strongest sides of the tournament.
        final = etl.pick_final(sample_matches)
        assert {final["home_team"], final["away_team"]} == {"Uruguay", "Brazil"}

    def test_points_are_awarded_three_for_a_win_one_for_a_draw(self):
        df = pd.DataFrame([
            ("A", "B", 1, 0), ("A", "C", 2, 2),
        ], columns=["home_team", "away_team", "home_score", "away_score"])
        points = etl.tournament_points(df)
        assert points == {"A": 4, "B": 0, "C": 1}


class TestCalibration:
    def test_draw_rate_falls_as_the_rating_gap_widens(self):
        rows = []
        # close matches drawn half the time, lopsided ones never
        for i in range(400):
            rows.append(("2000-01-01", 1500, 1500, 1, 1, 1))
        for i in range(400):
            rows.append(("2000-01-01", 1900, 1500, 3, 0, 1))
        df = pd.DataFrame(rows, columns=["date", "home_elo", "away_elo",
                                         "home_score", "away_score", "neutral"])
        cal = etl.calibrate_draw_model(df)
        assert cal.iloc[0]["draw_rate"] > cal.iloc[-1]["draw_rate"]

    def test_every_bucket_reports_a_valid_rate(self, ctx):
        from app.services import ratings
        for row in ratings.calibration_table():
            assert 0 <= row["draw_rate"] <= 1
            assert row["draws"] <= row["matches"]


class TestScoring:
    def test_a_perfect_forecast_scores_zero_brier(self):
        df = pd.DataFrame([("2000-01-01", 3000, 1000, 5, 0, 1)],
                          columns=["date", "home_elo", "away_elo",
                                   "home_score", "away_score", "neutral"])
        result = etl.score(df, {0: 0.0})
        assert result["accuracy"] == 1.0
        assert result["brier_score"] < 0.01
