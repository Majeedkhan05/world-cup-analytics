"""JSON API. The dashboard charts fetch from here, and it makes the data
usable by anything else (a notebook, a mobile client, curl)."""
from flask import Blueprint, jsonify, request

from app.services import analytics, ratings, predictor

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/overview")
def overview():
    return jsonify(analytics.overview())


@bp.get("/tournaments")
def tournaments():
    return jsonify(analytics.tournaments())


@bp.get("/goal-trend")
def goal_trend():
    return jsonify(analytics.goal_trend())


@bp.get("/titles")
def titles():
    return jsonify(analytics.title_counts())


@bp.get("/goal-minutes")
def goal_minutes():
    return jsonify(analytics.goal_minutes())


@bp.get("/host-advantage")
def host_advantage():
    return jsonify(analytics.host_advantage())


@bp.get("/rankings")
def rankings():
    return jsonify(ratings.rankings(limit=request.args.get("limit", 50, type=int)))


@bp.get("/teams")
def teams():
    return jsonify(analytics.teams_list())


@bp.get("/teams/<name>")
def team(name):
    record = analytics.team_record(name)
    if record is None:
        return jsonify({"error": f"unknown team: {name}"}), 404
    return jsonify({"record": record,
                    "honours": analytics.team_honours(name),
                    "by_edition": analytics.team_by_edition(name)})


@bp.get("/teams/<name>/rating-history")
def rating_history(name):
    return jsonify(ratings.rating_series(name))


@bp.get("/head-to-head")
def head_to_head():
    a, b = request.args.get("a"), request.args.get("b")
    if not a or not b:
        return jsonify({"error": "query params 'a' and 'b' are required"}), 400
    return jsonify(analytics.head_to_head(a, b))


@bp.get("/predict")
def predict():
    a, b = request.args.get("a"), request.args.get("b")
    neutral = request.args.get("neutral", "1") == "1"
    if not a or not b:
        return jsonify({"error": "query params 'a' and 'b' are required"}), 400
    result = predictor.predict(a, b, neutral)
    if result is None:
        return jsonify({"error": "unknown team"}), 404
    return jsonify(result)


@bp.get("/model")
def model():
    return jsonify({"metrics": predictor.metrics(),
                    "calibration": ratings.calibration_table()})


@bp.get("/records/scorers")
def scorers():
    return jsonify(analytics.top_scorers(request.args.get("limit", 25, type=int)))
