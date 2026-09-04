"""ETL pipeline: raw CSV files  ->  cleaned  ->  normalised SQLite database.

Run with:  python -m app.etl

Stages
------
extract   read the three source CSVs with pandas
transform clean types, build the team dimension, derive tournament summaries,
          replay 150 years of matches through the Elo engine
load      write every table into SQLite in one transaction
"""
import sys
import pandas as pd

from app.config import RAW_DIR, DB_PATH, WORLD_CUP, BASE_DIR, ELO_HOME_ADVANTAGE
from app.db import connect
from app.services.elo import EloEngine
from app.services.predictor import probabilities, BUCKET_SIZE


# --------------------------------------------------------------------- extract
def extract():
    results = pd.read_csv(RAW_DIR / "results.csv")
    goals = pd.read_csv(RAW_DIR / "goalscorers.csv")
    shootouts = pd.read_csv(RAW_DIR / "shootouts.csv")
    return results, goals, shootouts


# ------------------------------------------------------------------- transform
def clean_matches(results):
    """Type-cast, drop unplayed fixtures, add year and World Cup flag."""
    df = results.copy()
    df = df.dropna(subset=["home_score", "away_score"])
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["year"] = df["date"].str.slice(0, 4).astype(int)
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE").astype(int)
    df["is_world_cup"] = (df["tournament"] == WORLD_CUP).astype(int)
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    df["id"] = df.index + 1
    return df


def build_teams(matches):
    """The team dimension: every nation that ever appears, as a lookup table."""
    names = sorted(set(matches["home_team"]) | set(matches["away_team"]))
    return {name: i + 1 for i, name in enumerate(names)}


def clean_goals(goals, matches, team_ids):
    """Attach each goal to its match id via the (date, home, away) natural key."""
    key = matches[["id", "date", "home_team", "away_team"]]
    df = goals.merge(key, on=["date", "home_team", "away_team"], how="inner")
    df = df[df["team"].isin(team_ids)]
    df["team_id"] = df["team"].map(team_ids)
    for col in ("own_goal", "penalty"):
        df[col] = df[col].astype(str).str.upper().eq("TRUE").astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce")
    return df.rename(columns={"id": "match_id"})[
        ["match_id", "team_id", "scorer", "minute", "own_goal", "penalty"]
    ]


def clean_shootouts(shootouts, matches, team_ids):
    key = matches[["id", "date", "home_team", "away_team"]]
    df = shootouts.merge(key, on=["date", "home_team", "away_team"], how="inner")
    df = df[df["winner"].isin(team_ids)]
    df["winner_id"] = df["winner"].map(team_ids)
    return df.rename(columns={"id": "match_id"})[["match_id", "winner_id"]]


def tournament_points(group):
    """League points (3 win / 1 draw) for every team in one edition."""
    points = {}
    for r in group.itertuples():
        hp, ap = (3, 0) if r.home_score > r.away_score else \
                 (0, 3) if r.home_score < r.away_score else (1, 1)
        points[r.home_team] = points.get(r.home_team, 0) + hp
        points[r.away_team] = points.get(r.away_team, 0) + ap
    return points


def pick_final(group):
    """The deciding match of an edition.

    Normally that is simply the last match played. Two early editions (notably
    1950) ended in a final round-robin where several matches share the last
    date, so we break the tie by picking the fixture between the two strongest
    teams of the tournament.
    """
    last_date = group["date"].max()
    candidates = group[group["date"] == last_date]
    if len(candidates) == 1:
        return candidates.iloc[0]
    points = tournament_points(group)
    strength = candidates.apply(
        lambda r: points.get(r["home_team"], 0) + points.get(r["away_team"], 0), axis=1
    )
    return candidates.loc[strength.idxmax()]


def build_tournaments(matches, shootout_lookup, team_ids):
    """One summary row per World Cup edition.

    The champion is the winner of the deciding match; if it was drawn we fall
    back to the penalty shootout result.
    """
    wc = matches[matches["is_world_cup"] == 1]
    rows = []
    for year, group in wc.groupby("year"):
        final = pick_final(group)
        home, away = final["home_team"], final["away_team"]
        if final["home_score"] > final["away_score"]:
            champion, runner_up = home, away
        elif final["home_score"] < final["away_score"]:
            champion, runner_up = away, home
        else:
            winner = shootout_lookup.get(int(final["id"]))
            champion = winner or home
            runner_up = away if champion == home else home

        hosts = sorted({c for c in group["country"].dropna().unique()})
        teams = set(group["home_team"]) | set(group["away_team"])
        rows.append({
            "year": int(year),
            "host": ", ".join(hosts),
            "champion_id": team_ids[champion],
            "runner_up_id": team_ids[runner_up],
            "matches": len(group),
            "goals": int(group["home_score"].sum() + group["away_score"].sum()),
            "teams_count": len(teams),
            "final_date": final["date"],
        })
    return pd.DataFrame(rows)


def compute_elo(matches):
    """Replay every international match ever played through the Elo engine.

    Also writes each side's rating *as it stood before kick-off* back onto the
    matches frame - that is what the predictor is later calibrated against.
    """
    engine = EloEngine()
    engine.run(matches.to_dict("records"))
    pre = matches["id"].map(engine.pre_match)
    matches["home_elo"] = [p[0] for p in pre]
    matches["away_elo"] = [p[1] for p in pre]
    return engine


def calibrate_draw_model(matches):
    """Measure the real draw rate for each bucket of pre-match Elo gap.

    This is the only "training" the predictor does: no library, just counting
    what actually happened across 150 years of international football.
    """
    df = matches.copy()
    advantage = ELO_HOME_ADVANTAGE * (1 - df["neutral"])
    df["gap"] = ((df["home_elo"] + advantage) - df["away_elo"]).abs()
    df["bucket"] = (df["gap"] // BUCKET_SIZE).astype(int)
    df["is_draw"] = (df["home_score"] == df["away_score"]).astype(int)

    grouped = df.groupby("bucket").agg(matches=("is_draw", "size"),
                                       draws=("is_draw", "sum")).reset_index()
    # Buckets with very little data are unreliable; fold them into the last
    # well-populated bucket so the lookup stays smooth.
    reliable = grouped[grouped["matches"] >= 50]
    if len(reliable):
        cutoff = reliable["bucket"].max()
        tail = grouped[grouped["bucket"] > cutoff]
        grouped = grouped[grouped["bucket"] <= cutoff].copy()
        if len(tail):
            grouped.loc[grouped["bucket"] == cutoff, "matches"] += int(tail["matches"].sum())
            grouped.loc[grouped["bucket"] == cutoff, "draws"] += int(tail["draws"].sum())
    grouped["draw_rate"] = (grouped["draws"] / grouped["matches"]).round(4)
    grouped["gap_lo"] = grouped["bucket"] * BUCKET_SIZE
    grouped["gap_hi"] = grouped["gap_lo"] + BUCKET_SIZE
    return grouped


HOLDOUT_FROM = "2015-01-01"   # matches from here on are never used for fitting


def score(df, calibration):
    """Run the predictor over a set of matches and return accuracy + Brier score.

    Note that every prediction uses only the ratings each team held *before*
    that match, so this is a walk-forward evaluation rather than a peek ahead.
    """
    correct = brier = 0.0
    n = 0
    for r in df.itertuples():
        p_home, p_draw, p_away = probabilities(
            r.home_elo, r.away_elo, calibration, neutral=bool(r.neutral))
        actual = (1, 0, 0) if r.home_score > r.away_score else \
                 (0, 0, 1) if r.home_score < r.away_score else (0, 1, 0)
        predicted = max(zip((p_home, p_draw, p_away), (0, 1, 2)))[1]
        correct += actual[predicted]
        brier += sum((p - a) ** 2 for p, a in zip((p_home, p_draw, p_away), actual))
        n += 1

    home_wins = int((df["home_score"] > df["away_score"]).sum())
    return {
        "matches": float(n),
        "accuracy": round(correct / n, 4),
        "brier_score": round(brier / n, 4),
        "baseline_accuracy": round(home_wins / n, 4),
    }


def evaluate_model(matches, calibration_df):
    """Two evaluations, reported side by side.

    full     - every match the engine has ratings for
    holdout  - a clean train/test split: the draw model is re-calibrated using
               only matches before 2015, then scored on everything after it, so
               no part of the test set influenced the model.
    """
    df = matches[matches["home_elo"].notna()]
    full_cal = dict(zip(calibration_df["bucket"], calibration_df["draw_rate"]))
    full = score(df, full_cal)

    train = df[df["date"] < HOLDOUT_FROM]
    test = df[df["date"] >= HOLDOUT_FROM]
    holdout_cal = calibrate_draw_model(train)
    holdout = score(test, dict(zip(holdout_cal["bucket"], holdout_cal["draw_rate"])))

    return {
        "matches_evaluated": full["matches"],
        "accuracy": full["accuracy"],
        "brier_score": full["brier_score"],
        "baseline_accuracy": full["baseline_accuracy"],
        "holdout_matches": holdout["matches"],
        "holdout_accuracy": holdout["accuracy"],
        "holdout_brier_score": holdout["brier_score"],
        "holdout_baseline_accuracy": holdout["baseline_accuracy"],
    }


# ------------------------------------------------------------------------ load
def load(matches, team_ids, goals, shootouts, tournaments, engine,
         calibration, metrics, db_path=DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript((BASE_DIR / "app" / "schema.sql").read_text())

    conn.executemany("INSERT INTO teams (id, name) VALUES (?, ?)",
                     [(i, n) for n, i in team_ids.items()])

    conn.executemany(
        """INSERT INTO matches (id, date, year, tournament, home_team_id, away_team_id,
                                home_score, away_score, city, country, neutral,
                                is_world_cup, home_elo, away_elo)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(int(r.id), r.date, int(r.year), r.tournament,
          team_ids[r.home_team], team_ids[r.away_team],
          int(r.home_score), int(r.away_score), r.city, r.country,
          int(r.neutral), int(r.is_world_cup),
          round(r.home_elo, 2), round(r.away_elo, 2))
         for r in matches.itertuples()],
    )

    conn.executemany(
        """INSERT INTO goals (match_id, team_id, scorer, minute, own_goal, penalty)
           VALUES (?,?,?,?,?,?)""",
        [(int(r.match_id), int(r.team_id), r.scorer,
          None if pd.isna(r.minute) else float(r.minute),
          int(r.own_goal), int(r.penalty)) for r in goals.itertuples()],
    )

    conn.executemany("INSERT INTO shootouts (match_id, winner_id) VALUES (?,?)",
                     [(int(r.match_id), int(r.winner_id)) for r in shootouts.itertuples()])

    conn.executemany(
        """INSERT INTO tournaments (year, host, champion_id, runner_up_id,
                                    matches, goals, teams_count, final_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        [(int(r.year), r.host, int(r.champion_id), int(r.runner_up_id),
          int(r.matches), int(r.goals), int(r.teams_count), r.final_date)
         for r in tournaments.itertuples()],
    )

    conn.executemany(
        """INSERT INTO elo_ratings (team_id, rating, matches, peak_rating, peak_date)
           VALUES (?,?,?,?,?)""",
        [(team_ids[t], round(rating, 2), engine.played[t],
          round(engine.peak[t][0], 2), engine.peak[t][1])
         for t, rating in engine.ratings.items()],
    )

    conn.executemany("INSERT INTO elo_history (team_id, date, rating) VALUES (?,?,?)",
                     [(team_ids[t], d, round(r, 2)) for t, d, r in engine.history])

    conn.executemany(
        """INSERT INTO draw_calibration (bucket, gap_lo, gap_hi, matches, draws, draw_rate)
           VALUES (?,?,?,?,?,?)""",
        [(int(r.bucket), int(r.gap_lo), int(r.gap_hi), int(r.matches),
          int(r.draws), float(r.draw_rate)) for r in calibration.itertuples()])

    conn.executemany("INSERT INTO model_metrics (name, value) VALUES (?,?)",
                     list(metrics.items()))

    conn.commit()
    conn.close()


def run():
    print("extract  ...", end=" ", flush=True)
    results, goals_raw, shootouts_raw = extract()
    print(f"{len(results):,} rows")

    print("transform...", end=" ", flush=True)
    matches = clean_matches(results)
    team_ids = build_teams(matches)
    goals = clean_goals(goals_raw, matches, team_ids)
    shootouts = clean_shootouts(shootouts_raw, matches, team_ids)
    shootout_lookup = {}
    id_to_team = {v: k for k, v in team_ids.items()}
    for r in shootouts.itertuples():
        shootout_lookup[int(r.match_id)] = id_to_team[int(r.winner_id)]
    tournaments = build_tournaments(matches, shootout_lookup, team_ids)
    engine = compute_elo(matches)
    calibration = calibrate_draw_model(matches)
    print(f"{len(team_ids)} teams, {len(tournaments)} World Cups")

    print("evaluate ...", end=" ", flush=True)
    metrics = evaluate_model(matches, calibration)
    print(f"full {metrics['accuracy']:.1%} | "
          f"held-out {metrics['holdout_accuracy']:.1%} "
          f"vs baseline {metrics['holdout_baseline_accuracy']:.1%} "
          f"(Brier {metrics['holdout_brier_score']:.3f}, "
          f"n={metrics['holdout_matches']:.0f})")

    print("load     ...", end=" ", flush=True)
    load(matches, team_ids, goals, shootouts, tournaments, engine, calibration, metrics)
    print(f"-> {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
