"""Tests for the analytics queries, run against the real database."""
import pytest

from app.services import analytics, ratings


class TestOverview:
    def test_headline_numbers_are_consistent(self, ctx):
        o = analytics.overview()
        assert o["editions"] == 23
        assert o["first_year"] == 1930
        assert o["matches"] > 1000
        assert o["goals_per_match"] == pytest.approx(o["goals"] / o["matches"], abs=0.01)

    def test_world_cup_is_a_subset_of_all_football(self, ctx):
        o = analytics.overview()
        assert o["matches"] < o["total_matches_all"]


class TestTournaments:
    def test_one_row_per_edition_in_chronological_order(self, ctx):
        rows = analytics.tournaments()
        years = [r["year"] for r in rows]
        assert years == sorted(years)
        assert len(years) == len(set(years))

    def test_champions_match_the_historical_record(self, ctx):
        champions = {r["year"]: r["champion"] for r in analytics.tournaments()}
        assert champions[1930] == "Uruguay"
        assert champions[1950] == "Uruguay"     # decided by a final round-robin
        assert champions[2014] == "Germany"
        assert champions[2018] == "France"
        assert champions[2022] == "Argentina"   # decided on penalties

    def test_goals_per_match_is_plausible(self, ctx):
        assert all(1.5 < r["goals_per_match"] < 6 for r in analytics.tournaments())

    def test_titles_add_up_to_the_number_of_editions(self, ctx):
        assert sum(t["titles"] for t in analytics.title_counts()) == 23


class TestTeamRecords:
    def test_wins_draws_and_losses_account_for_every_match(self, ctx):
        r = analytics.team_record("Brazil")
        assert r["won"] + r["drawn"] + r["lost"] == r["played"]

    def test_derived_fields_are_correct(self, ctx):
        r = analytics.team_record("Germany")
        assert r["goal_diff"] == r["goals_for"] - r["goals_against"]
        assert r["win_pct"] == pytest.approx(100 * r["won"] / r["played"], abs=0.1)

    def test_all_time_record_includes_more_than_the_world_cup(self, ctx):
        assert (analytics.team_record("Brazil", world_cup_only=False)["played"]
                > analytics.team_record("Brazil")["played"])

    def test_a_team_that_never_qualified_has_no_record(self, ctx):
        assert analytics.team_record("India") is None

    def test_honours_are_consistent_with_the_title_count(self, ctx):
        honours = analytics.team_honours("Brazil")
        titles = [h for h in honours if h["result"] == "Champion"]
        assert len(titles) == 5

    def test_per_edition_totals_match_the_overall_record(self, ctx):
        by_edition = analytics.team_by_edition("Italy")
        assert sum(e["played"] for e in by_edition) == analytics.team_record("Italy")["played"]


class TestHeadToHead:
    def test_results_are_symmetric(self, ctx):
        one = analytics.head_to_head("Brazil", "Argentina")["summary"]
        other = analytics.head_to_head("Argentina", "Brazil")["summary"]
        assert one["played"] == other["played"]
        assert one["a_wins"] == other["b_wins"]
        assert one["a_goals"] == other["b_goals"]

    def test_every_meeting_is_classified(self, ctx):
        s = analytics.head_to_head("Germany", "Italy")["summary"]
        assert s["a_wins"] + s["b_wins"] + s["draws"] == s["played"]

    def test_teams_that_never_met_return_an_empty_record(self, ctx):
        assert analytics.head_to_head("Brazil", "Nowhereland")["summary"]["played"] == 0

    def test_world_cup_filter_narrows_the_set(self, ctx):
        assert (analytics.head_to_head("Brazil", "Argentina", world_cup_only=True)["summary"]["played"]
                <= analytics.head_to_head("Brazil", "Argentina")["summary"]["played"])


class TestRecords:
    def test_scorers_are_ranked_and_credible(self, ctx):
        scorers = analytics.top_scorers(10)
        goals = [s["goals"] for s in scorers]
        assert goals == sorted(goals, reverse=True)
        names = [s["scorer"] for s in scorers]
        assert "Miroslav Klose" in names   # the long-standing record holder

    def test_goal_minute_buckets_cover_the_whole_match(self, ctx):
        buckets = analytics.goal_minutes()
        assert [b["window"] for b in buckets] == ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90+"]
        assert all(b["goals"] > 0 for b in buckets)

    def test_biggest_wins_are_ordered_by_margin(self, ctx):
        margins = [m["margin"] for m in analytics.biggest_wins(10)]
        assert margins == sorted(margins, reverse=True)

    def test_hosts_outperform_visitors(self, ctx):
        rows = {r["side"]: r for r in analytics.host_advantage()}
        assert rows["Host nation"]["win_pct"] > rows["Visiting nation"]["win_pct"]


class TestRatings:
    def test_rankings_are_sorted_and_numbered(self, ctx):
        rows = ratings.rankings(limit=20)
        assert [r["rank"] for r in rows] == list(range(1, 21))
        assert [r["rating"] for r in rows] == sorted((r["rating"] for r in rows), reverse=True)

    def test_peak_is_never_below_the_current_rating(self, ctx):
        assert all(r["peak_rating"] >= r["rating"] for r in ratings.rankings(limit=40))

    def test_rating_history_is_chronological(self, ctx):
        dates = [p["date"] for p in ratings.rating_series("Brazil")]
        assert dates == sorted(dates)

    def test_calibration_shows_draws_falling_as_the_gap_grows(self, ctx):
        table = ratings.calibration_table()
        assert table[0]["draw_rate"] > table[-1]["draw_rate"]
