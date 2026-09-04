"""Tests for turning ratings into probabilities."""
import pytest

from app.services import predictor


CAL = {0: 0.28, 1: 0.26, 2: 0.22, 3: 0.18, 4: 0.12}


class TestBuckets:
    def test_gap_maps_to_bucket(self):
        assert predictor.bucket_for(0) == 0
        assert predictor.bucket_for(49) == 0
        assert predictor.bucket_for(50) == 1
        assert predictor.bucket_for(220) == 4

    def test_sign_of_the_gap_is_irrelevant(self):
        assert predictor.bucket_for(-180) == predictor.bucket_for(180)

    def test_gap_beyond_the_table_falls_back_to_the_last_bucket(self):
        assert predictor.draw_probability(5000, CAL) == CAL[4]

    def test_empty_calibration_still_returns_something_sane(self):
        assert 0 < predictor.draw_probability(100, {}) < 1


class TestProbabilities:
    def test_probabilities_form_a_distribution(self):
        p = predictor.probabilities(1800, 1600, CAL)
        assert sum(p) == pytest.approx(1.0)
        assert all(0 <= x <= 1 for x in p)

    def test_evenly_matched_teams_are_symmetric(self):
        p_home, p_draw, p_away = predictor.probabilities(1600, 1600, CAL, neutral=True)
        assert p_home == pytest.approx(p_away)

    def test_the_stronger_team_is_favoured(self):
        p_home, _, p_away = predictor.probabilities(1900, 1500, CAL, neutral=True)
        assert p_home > p_away

    def test_home_advantage_shifts_the_odds(self):
        home = predictor.probabilities(1600, 1600, CAL, neutral=False)[0]
        neutral = predictor.probabilities(1600, 1600, CAL, neutral=True)[0]
        assert home > neutral

    def test_evenly_matched_teams_draw_more_often(self):
        close = predictor.probabilities(1600, 1600, CAL)[1]
        lopsided = predictor.probabilities(1600, 1400, CAL)[1]
        assert close > lopsided

    def test_extreme_mismatch_stays_a_valid_distribution(self):
        # Without clamping this is where probabilities would go negative.
        p = predictor.probabilities(2400, 1000, CAL)
        assert sum(p) == pytest.approx(1.0)
        assert all(x >= 0 for x in p)


class TestPredictAgainstTheDatabase:
    def test_known_team_returns_a_full_prediction(self, ctx):
        result = predictor.predict("Brazil", "Argentina")
        assert result["team_a"] == "Brazil"
        assert result["pct_a"] + result["pct_draw"] + result["pct_b"] == pytest.approx(100, abs=0.2)

    def test_unknown_team_returns_none(self, ctx):
        assert predictor.predict("Nowhereland", "Brazil") is None

    def test_favourite_matches_the_probabilities(self, ctx):
        result = predictor.predict("Brazil", "Bolivia")
        assert result["favourite"] == "Brazil"
        assert result["p_a"] > result["p_b"]

    def test_swapping_the_teams_mirrors_the_result(self, ctx):
        one = predictor.predict("Spain", "Brazil", neutral=True)
        other = predictor.predict("Brazil", "Spain", neutral=True)
        assert one["p_a"] == pytest.approx(other["p_b"], abs=1e-4)

    def test_metrics_are_available(self, ctx):
        m = predictor.metrics()
        assert 0 < m["holdout_accuracy"] < 1
        assert m["holdout_accuracy"] > m["holdout_baseline_accuracy"]
