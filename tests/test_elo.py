"""Unit tests for the rating engine. No database, no Flask - pure functions."""
import pytest

from app.services import elo


class TestExpectedScore:
    def test_equal_ratings_are_a_coin_flip(self):
        assert elo.expected_score(1500, 1500) == pytest.approx(0.5)

    def test_four_hundred_point_gap_is_ten_to_one(self):
        # The defining property of the Elo curve.
        e = elo.expected_score(1900, 1500)
        assert e / (1 - e) == pytest.approx(10.0, rel=1e-6)

    def test_expectations_of_both_sides_sum_to_one(self):
        assert (elo.expected_score(1700, 1450)
                + elo.expected_score(1450, 1700)) == pytest.approx(1.0)

    def test_home_advantage_helps_the_home_side(self):
        assert elo.expected_score(1500, 1500, 65) > 0.5


class TestMarginFactor:
    def test_one_goal_win_is_neutral(self):
        assert elo.margin_factor(1, 0) == 1.0

    def test_bigger_wins_count_for_more(self):
        assert elo.margin_factor(4, 0) > elo.margin_factor(2, 0)

    def test_factor_is_capped(self):
        assert elo.margin_factor(15, 0, cap=3.0) == 3.0

    def test_direction_does_not_matter(self):
        assert elo.margin_factor(0, 4) == elo.margin_factor(4, 0)


class TestOutcome:
    @pytest.mark.parametrize("h,a,expected", [(2, 1, 1.0), (1, 2, 0.0), (1, 1, 0.5)])
    def test_result_encoding(self, h, a, expected):
        assert elo.outcome(h, a) == expected


class TestUpdatePair:
    def test_ratings_are_zero_sum(self):
        before = 1500 + 1500
        new_h, new_a = elo.update_pair(1500, 1500, 2, 0)
        assert new_h + new_a == pytest.approx(before)

    def test_winner_gains_and_loser_loses(self):
        new_h, new_a = elo.update_pair(1500, 1500, 3, 1, neutral=True)
        assert new_h > 1500 and new_a < 1500

    def test_a_draw_transfers_points_to_the_underdog(self):
        new_h, new_a = elo.update_pair(1800, 1400, 1, 1, neutral=True)
        assert new_h < 1800 and new_a > 1400

    def test_beating_a_stronger_team_is_worth_more(self):
        upset, _ = elo.update_pair(1400, 1800, 1, 0, neutral=True)
        routine, _ = elo.update_pair(1800, 1400, 1, 0, neutral=True)
        assert (upset - 1400) > (routine - 1800)

    def test_world_cup_moves_ratings_more_than_a_friendly(self):
        wc, _ = elo.update_pair(1500, 1500, 1, 0, "FIFA World Cup", neutral=True)
        fr, _ = elo.update_pair(1500, 1500, 1, 0, "Friendly", neutral=True)
        assert wc - 1500 > fr - 1500


class TestEngine:
    def _match(self, home, away, hs, aws, date="2020-01-01"):
        return {"id": hash((home, away, date)) & 0xFFFF, "date": date,
                "home_team": home, "away_team": away,
                "home_score": hs, "away_score": aws,
                "tournament": "Friendly", "neutral": True}

    def test_unseen_team_starts_at_the_base_rating(self):
        assert elo.EloEngine().rating("Nowhereland") == elo.ELO_START

    def test_consistent_winner_climbs_the_table(self):
        engine = elo.EloEngine()
        engine.run([self._match("A", "B", 2, 0, f"2020-01-{d:02d}") for d in range(1, 11)])
        assert engine.rating("A") > engine.rating("B")
        table = engine.table(min_matches=1)
        assert table[0]["team"] == "A"
        assert table[0]["rank"] == 1

    def test_pre_match_ratings_are_recorded_before_the_update(self):
        engine = elo.EloEngine()
        m = self._match("A", "B", 3, 0)
        engine.process(m)
        assert engine.pre_match[m["id"]] == (elo.ELO_START, elo.ELO_START)
        assert engine.rating("A") > elo.ELO_START

    def test_peak_rating_is_tracked(self):
        engine = elo.EloEngine()
        engine.run([self._match("A", "B", 5, 0, "2020-01-01"),
                    self._match("A", "B", 0, 5, "2020-01-02")])
        peak, date = engine.peak["A"]
        assert peak > engine.rating("A")
        assert date == "2020-01-01"

    def test_table_hides_teams_with_too_few_matches(self):
        engine = elo.EloEngine().run([self._match("A", "B", 1, 0)])
        assert engine.table(min_matches=5) == []
