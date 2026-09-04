"""Analytics queries.

Every function returns plain Python lists/dicts so it can be handed straight
to a Jinja template or serialised as JSON by the API layer. All the heavy
lifting is done by SQL against the pre-built database.
"""
from app.db import query

WC = "is_world_cup = 1"


# ----------------------------------------------------------------- headline
def overview():
    """Top-line numbers for the dashboard KPI cards."""
    row = query(f"""
        SELECT COUNT(*) AS matches,
               SUM(home_score + away_score) AS goals,
               MIN(year) AS first_year,
               MAX(year) AS last_year
        FROM matches WHERE {WC}""", one=True)
    editions = query("SELECT COUNT(*) AS n FROM tournaments", one=True)["n"]
    teams = query(f"""
        SELECT COUNT(DISTINCT team_id) AS n FROM team_matches WHERE {WC}""", one=True)["n"]
    row.update(
        editions=editions,
        teams=teams,
        goals_per_match=round(row["goals"] / row["matches"], 2),
        total_matches_all=query("SELECT COUNT(*) AS n FROM matches", one=True)["n"],
    )
    return row


def tournaments():
    """Every World Cup edition with host, champion and scoring rate."""
    return query("""
        SELECT t.year, t.host, t.matches, t.goals, t.teams_count, t.final_date,
               c.name AS champion, r.name AS runner_up,
               ROUND(CAST(t.goals AS REAL) / t.matches, 2) AS goals_per_match
        FROM tournaments t
        JOIN teams c ON c.id = t.champion_id
        JOIN teams r ON r.id = t.runner_up_id
        ORDER BY t.year""")


def title_counts():
    """Most successful nations: titles won and finals reached."""
    return query("""
        SELECT te.name AS team,
               SUM(t.champion_id  = te.id) AS titles,
               SUM(t.runner_up_id = te.id) AS runner_ups,
               COUNT(*) AS finals
        FROM tournaments t
        JOIN teams te ON te.id IN (t.champion_id, t.runner_up_id)
        GROUP BY te.id
        ORDER BY titles DESC, finals DESC, team""")


def goal_trend():
    """Goals per match by edition — the classic 'football got tighter' chart."""
    return query("""
        SELECT year, matches, goals,
               ROUND(CAST(goals AS REAL) / matches, 2) AS goals_per_match
        FROM tournaments ORDER BY year""")


# --------------------------------------------------------------------- teams
def teams_list(world_cup_only=True):
    """Team names for dropdowns, ordered by how often they have played."""
    where = f"WHERE {WC}" if world_cup_only else ""
    return [r["name"] for r in query(f"""
        SELECT t.name, COUNT(*) AS n
        FROM team_matches tm JOIN teams t ON t.id = tm.team_id
        {where}
        GROUP BY t.id ORDER BY n DESC, t.name""")]


def team_record(team, world_cup_only=True):
    """Aggregate W/D/L record for one nation."""
    where = f"AND {WC}" if world_cup_only else ""
    row = query(f"""
        SELECT COUNT(*)        AS played,
               SUM(gf > ga)    AS won,
               SUM(gf = ga)    AS drawn,
               SUM(gf < ga)    AS lost,
               SUM(gf)         AS goals_for,
               SUM(ga)         AS goals_against,
               COUNT(DISTINCT year) AS editions
        FROM team_matches tm JOIN teams t ON t.id = tm.team_id
        WHERE t.name = ? {where}""", (team,), one=True)
    if not row or not row["played"]:
        return None
    row["team"] = team
    row["goal_diff"] = row["goals_for"] - row["goals_against"]
    row["win_pct"] = round(100 * row["won"] / row["played"], 1)
    row["points_per_match"] = round((3 * row["won"] + row["drawn"]) / row["played"], 2)
    return row


def team_honours(team):
    """Titles and runner-up finishes for one nation."""
    return query("""
        SELECT t.year, t.host,
               CASE WHEN c.name = ? THEN 'Champion' ELSE 'Runner-up' END AS result,
               CASE WHEN c.name = ? THEN r.name ELSE c.name END AS opponent
        FROM tournaments t
        JOIN teams c ON c.id = t.champion_id
        JOIN teams r ON r.id = t.runner_up_id
        WHERE c.name = ? OR r.name = ?
        ORDER BY t.year""", (team, team, team, team))


def team_matches(team, limit=200):
    """A nation's World Cup matches, most recent first."""
    return query(f"""
        SELECT tm.date, tm.year, o.name AS opponent, tm.gf, tm.ga, tm.city, tm.country,
               CASE WHEN tm.gf > tm.ga THEN 'W'
                    WHEN tm.gf < tm.ga THEN 'L' ELSE 'D' END AS result
        FROM team_matches tm
        JOIN teams t ON t.id = tm.team_id
        JOIN teams o ON o.id = tm.opponent_id
        WHERE t.name = ? AND {WC}
        ORDER BY tm.date DESC LIMIT ?""", (team, limit))


def team_by_edition(team):
    """Per-edition summary for a nation's World Cup campaigns."""
    return query(f"""
        SELECT tm.year, COUNT(*) AS played, SUM(tm.gf > tm.ga) AS won,
               SUM(tm.gf = tm.ga) AS drawn, SUM(tm.gf < tm.ga) AS lost,
               SUM(tm.gf) AS goals_for, SUM(tm.ga) AS goals_against
        FROM team_matches tm JOIN teams t ON t.id = tm.team_id
        WHERE t.name = ? AND {WC}
        GROUP BY tm.year ORDER BY tm.year""", (team,))


# ------------------------------------------------------------- head to head
def head_to_head(team_a, team_b, world_cup_only=False):
    """Every meeting between two nations, plus the aggregate record."""
    where = f"AND m.{WC}" if world_cup_only else ""
    matches = query(f"""
        SELECT m.date, m.year, m.tournament, m.city, m.country,
               h.name AS home_team, a.name AS away_team, m.home_score, m.away_score
        FROM matches m
        JOIN teams h ON h.id = m.home_team_id
        JOIN teams a ON a.id = m.away_team_id
        WHERE ((h.name = ? AND a.name = ?) OR (h.name = ? AND a.name = ?)) {where}
        ORDER BY m.date DESC""", (team_a, team_b, team_b, team_a))

    tally = {"team_a": team_a, "team_b": team_b, "played": len(matches),
             "a_wins": 0, "b_wins": 0, "draws": 0, "a_goals": 0, "b_goals": 0}
    for m in matches:
        a_gf = m["home_score"] if m["home_team"] == team_a else m["away_score"]
        b_gf = m["home_score"] if m["home_team"] == team_b else m["away_score"]
        tally["a_goals"] += a_gf
        tally["b_goals"] += b_gf
        if a_gf > b_gf:
            tally["a_wins"] += 1
        elif b_gf > a_gf:
            tally["b_wins"] += 1
        else:
            tally["draws"] += 1
    return {"summary": tally, "matches": matches}


# --------------------------------------------------------------------- goals
def top_scorers(limit=20):
    """All-time World Cup goalscorers (own goals excluded)."""
    return query(f"""
        SELECT g.scorer, t.name AS team, COUNT(*) AS goals,
               SUM(g.penalty) AS penalties,
               MIN(m.year) AS first_year, MAX(m.year) AS last_year
        FROM goals g
        JOIN matches m ON m.id = g.match_id
        JOIN teams t   ON t.id = g.team_id
        WHERE m.{WC} AND g.own_goal = 0 AND g.scorer IS NOT NULL
        GROUP BY g.scorer, t.id
        ORDER BY goals DESC, g.scorer LIMIT ?""", (limit,))


def goal_minutes():
    """When are World Cup goals scored? Bucketed into 15-minute blocks."""
    rows = query(f"""
        SELECT CAST(MIN(minute, 90) AS INTEGER) / 15 AS bucket, COUNT(*) AS goals
        FROM goals g JOIN matches m ON m.id = g.match_id
        WHERE m.{WC} AND g.minute IS NOT NULL
        GROUP BY bucket ORDER BY bucket""")
    labels = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90+"]
    counts = {int(r["bucket"]): r["goals"] for r in rows}
    return [{"window": lab, "goals": counts.get(i, 0)} for i, lab in enumerate(labels)]


def biggest_wins(limit=10):
    """The most lopsided results in World Cup history."""
    return query(f"""
        SELECT m.date, m.year, h.name AS home_team, a.name AS away_team,
               m.home_score, m.away_score,
               ABS(m.home_score - m.away_score) AS margin
        FROM matches m
        JOIN teams h ON h.id = m.home_team_id
        JOIN teams a ON a.id = m.away_team_id
        WHERE m.{WC}
        ORDER BY margin DESC, (m.home_score + m.away_score) DESC LIMIT ?""", (limit,))


def highest_scoring(limit=10):
    """Matches with the most total goals."""
    return query(f"""
        SELECT m.date, m.year, h.name AS home_team, a.name AS away_team,
               m.home_score, m.away_score,
               (m.home_score + m.away_score) AS total
        FROM matches m
        JOIN teams h ON h.id = m.home_team_id
        JOIN teams a ON a.id = m.away_team_id
        WHERE m.{WC}
        ORDER BY total DESC, m.date LIMIT ?""", (limit,))


# ------------------------------------------------------------ host advantage
def host_advantage():
    """Do hosts really do better? Compare host results against everyone else."""
    return query(f"""
        SELECT CASE WHEN tm.country = ho.name THEN 'Host nation' ELSE 'Visiting nation' END AS side,
               COUNT(*)     AS played,
               SUM(tm.gf > tm.ga) AS won,
               SUM(tm.gf = tm.ga) AS drawn,
               SUM(tm.gf < tm.ga) AS lost,
               ROUND(100.0 * SUM(tm.gf > tm.ga) / COUNT(*), 1) AS win_pct,
               ROUND(AVG(tm.gf), 2) AS avg_scored
        FROM team_matches tm
        JOIN teams ho ON ho.id = tm.team_id
        WHERE tm.{WC}
        GROUP BY side ORDER BY side""")


def shootout_stats():
    """Penalty shootouts at World Cups."""
    return query(f"""
        SELECT m.year, m.date, h.name AS home_team, a.name AS away_team,
               m.home_score, m.away_score, w.name AS winner
        FROM shootouts s
        JOIN matches m ON m.id = s.match_id
        JOIN teams h ON h.id = m.home_team_id
        JOIN teams a ON a.id = m.away_team_id
        JOIN teams w ON w.id = s.winner_id
        WHERE m.{WC} ORDER BY m.date DESC""")
