"""HTML pages. Each route just gathers data from the services and renders."""
from flask import Blueprint, render_template, request, abort

from app.services import analytics, ratings, predictor

bp = Blueprint("pages", __name__)


@bp.app_context_processor
def inject_nav():
    """Team list is needed by the search boxes on every page."""
    return {"all_teams": analytics.teams_list(world_cup_only=False)}


@bp.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        overview=analytics.overview(),
        goal_trend=analytics.goal_trend(),
        titles=[t for t in analytics.title_counts() if t["titles"] > 0],
        finals=analytics.title_counts()[:12],
        minutes=analytics.goal_minutes(),
        hosts=analytics.host_advantage(),
        top_rated=ratings.rankings(limit=10),
        recent=analytics.tournaments()[-6:][::-1],
    )


@bp.route("/tournaments")
def tournaments():
    return render_template("tournaments.html",
                           tournaments=analytics.tournaments()[::-1],
                           trend=analytics.goal_trend())


@bp.route("/teams")
def teams():
    return render_template("teams.html", teams=analytics.teams_list())


@bp.route("/teams/<name>")
def team_detail(name):
    record = analytics.team_record(name)
    if record is None:
        abort(404)
    return render_template(
        "team.html",
        team=name,
        record=record,
        all_time=analytics.team_record(name, world_cup_only=False),
        honours=analytics.team_honours(name),
        by_edition=analytics.team_by_edition(name),
        matches=analytics.team_matches(name, limit=30),
        series=ratings.rating_series(name),
        rating=predictor.team_rating(name),
    )


@bp.route("/rankings")
def rankings():
    return render_template("rankings.html",
                           rankings=ratings.rankings(limit=60),
                           metrics=predictor.metrics())


@bp.route("/head-to-head")
def head_to_head():
    a = request.args.get("a", "Brazil")
    b = request.args.get("b", "Argentina")
    result = analytics.head_to_head(a, b) if a and b and a != b else None
    return render_template("head_to_head.html", a=a, b=b, result=result,
                           prediction=predictor.predict(a, b) if result else None)


@bp.route("/predict")
def predict():
    a = request.args.get("a", "Spain")
    b = request.args.get("b", "Brazil")
    neutral = request.args.get("neutral", "1") == "1"
    prediction = predictor.predict(a, b, neutral) if a != b else None
    return render_template("predict.html", a=a, b=b, neutral=neutral,
                           prediction=prediction,
                           metrics=predictor.metrics(),
                           calibration=ratings.calibration_table())


@bp.route("/records")
def records():
    return render_template("records.html",
                           scorers=analytics.top_scorers(25),
                           biggest=analytics.biggest_wins(10),
                           highest=analytics.highest_scoring(10),
                           shootouts=analytics.shootout_stats())


@bp.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404
