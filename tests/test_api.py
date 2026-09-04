"""Integration tests: every HTTP route, through Flask's test client."""
import pytest


PAGES = ["/", "/tournaments", "/teams", "/teams/Brazil", "/rankings",
         "/head-to-head", "/predict", "/records"]


class TestPages:
    @pytest.mark.parametrize("path", PAGES)
    def test_page_renders(self, client, path):
        r = client.get(path)
        assert r.status_code == 200
        assert b"<html" in r.data

    def test_unknown_team_gives_a_404_page(self, client):
        r = client.get("/teams/Nowhereland")
        assert r.status_code == 404
        assert b"Not found" in r.data

    def test_head_to_head_accepts_two_teams(self, client):
        r = client.get("/head-to-head?a=Germany&b=Italy")
        assert r.status_code == 200
        assert b"Germany" in r.data and b"Italy" in r.data

    def test_predictor_renders_probabilities(self, client):
        r = client.get("/predict?a=Spain&b=Brazil&neutral=1")
        assert r.status_code == 200
        assert b"Match predictor" in r.data


class TestJsonApi:
    def test_overview_shape(self, client):
        data = client.get("/api/overview").get_json()
        assert set(["editions", "matches", "goals", "goals_per_match"]) <= set(data)

    def test_tournaments_returns_every_edition(self, client):
        assert len(client.get("/api/tournaments").get_json()) == 23

    def test_rankings_respects_the_limit(self, client):
        assert len(client.get("/api/rankings?limit=7").get_json()) == 7

    def test_team_endpoint_bundles_record_and_honours(self, client):
        data = client.get("/api/teams/Brazil").get_json()
        assert data["record"]["played"] > 0
        assert len(data["honours"]) > 0

    def test_unknown_team_returns_404_json(self, client):
        r = client.get("/api/teams/Nowhereland")
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_predict_returns_a_distribution(self, client):
        d = client.get("/api/predict?a=France&b=Morocco").get_json()
        assert d["p_a"] + d["p_draw"] + d["p_b"] == pytest.approx(1.0, abs=1e-3)

    def test_missing_parameters_are_rejected(self, client):
        assert client.get("/api/predict?a=France").status_code == 400
        assert client.get("/api/head-to-head").status_code == 400

    def test_model_endpoint_exposes_metrics_and_calibration(self, client):
        d = client.get("/api/model").get_json()
        assert "holdout_accuracy" in d["metrics"]
        assert len(d["calibration"]) > 3

    def test_rating_history_is_a_time_series(self, client):
        series = client.get("/api/teams/Italy/rating-history").get_json()
        assert len(series) > 10
        assert set(series[0]) == {"date", "rating"}

    def test_responses_are_json(self, client):
        assert client.get("/api/overview").content_type.startswith("application/json")
