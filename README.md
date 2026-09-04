# World Cup Analytics

An analytics platform for international football, built on **49,547 real matches played
between 1872 and 2026**. It answers historical questions about the FIFA World Cup, ranks
every national team with an Elo rating engine, and predicts the outcome of any fixture
you ask for.

> Software Engineering course project · Project #11 — FIFA World Cup Analytics

**Presentation:** [`docs/World-Cup-Analytics-Presentation.pptx`](docs/World-Cup-Analytics-Presentation.pptx)
([PDF](docs/World-Cup-Analytics-Presentation.pdf)) — 12 slides with speaker notes.
**Docs:** [SRS](docs/SRS.md) · [Design](docs/DESIGN.md) · [Testing](docs/TESTING.md) · [Viva notes](docs/PRESENTATION.md)

---

## What it does

| | |
|---|---|
| **Dashboard** | Headline statistics, scoring trends across 23 editions, when goals are scored, host advantage |
| **Tournaments** | Every World Cup from 1930 to 2026 — host, champion, runner-up, scoring rate |
| **Teams** | Full record for all 86 nations that have played a World Cup, plus a 150-year rating history |
| **Rankings** | Elo world rankings computed from the complete match archive |
| **Head-to-head** | Every meeting between any two nations, ever |
| **Predictor** | Win / draw / loss probabilities for any fixture, with the reasoning shown |
| **REST API** | Every figure on the site is also available as JSON |

---

## The interesting part: the rating and prediction model

Most of this project is ordinary data engineering. The part worth explaining is the model,
and it is deliberately small enough to fit on a whiteboard.

### 1. Elo ratings

Every team starts at 1500. For each of the 49,547 matches, in chronological order:

```
E = 1 / (1 + 10^(-(R_home + H - R_away) / 400))     what the ratings expected
S = 1 / 0.5 / 0                                      what actually happened
R' = R + K x weight x margin x (S - E)               the correction
```

A team gains points only by doing **better than its rating predicted**. Beating a much
stronger side moves the rating a lot; beating a much weaker one barely moves it at all.
Elo is zero-sum, so whatever the winner gains, the loser loses.

Three multipliers shape how fast ratings move:

- **K** — the base learning rate.
- **weight** — a World Cup match counts for 2.0, a friendly for 0.7.
- **margin** — `sqrt(goal difference)`, capped, so a 5–0 counts for more than a 1–0 but a
  9–0 does not count for absurdly more.

These were **not guessed**. `scripts/tune_elo.py` sweeps 96 combinations, replays the
entire match history for each, and scores every one on matches the model never saw
(see below). The best settings are the ones in `app/config.py`.

### 2. From one rating to three probabilities

Elo gives a single number `E`, which blends wins and draws. To split it into win / draw /
loss we need to know how often draws actually happen — so that is **measured from the data
rather than assumed**:

Every historical match is bucketed by the rating gap that existed *before kick-off*, and
the real draw rate in each bucket is counted. The result is the visible finding that
**evenly matched teams draw roughly twice as often as mismatched ones**.

Then, because `E = P(win) + ½·P(draw)`:

```
P(draw) = measured draw rate for this rating gap
P(win)  = E - P(draw)/2
P(loss) = 1 - P(win) - P(draw)
```

### 3. Does it actually work?

The draw model is fitted **only on matches before 2015**, then scored on the 11,130
matches played since — so nothing in the test set influenced the model.

| Metric | Result |
|---|---|
| Accuracy on unseen matches | **60.1%** |
| Baseline (always pick the home team) | 47.7% |
| Brier score (lower is better; 0.667 = uninformed guessing) | **0.516** |
| Matches in the test set | 11,130 |

Every prediction uses only the ratings each team held *before* that match, so this is a
walk-forward evaluation, not a peek at the answer.

---

## Architecture

```
data/raw/*.csv
      |
      v
  ETL pipeline  (app/etl.py)          extract -> transform -> load
      |                               cleans types, builds the team dimension,
      |                               replays 150 years through the Elo engine,
      |                               calibrates and scores the model
      v
  SQLite database (data/worldcup.sqlite3)
      |
      v
  Service layer (app/services/)       analytics · elo · predictor · ratings
      |                               plain SQL + pure Python, no ORM
      v
  Routes (app/routes/)                pages.py renders HTML · api.py returns JSON
      |
      v
  Browser                             Jinja templates + Chart.js
```

The layering is strict: **routes never touch SQL, services never touch HTTP.** That is what
makes the whole thing testable — the Elo engine has no database, and the analytics layer
has no web server.

### Project layout

```
app/
  config.py         all tunable constants in one place
  schema.sql        normalised database schema
  db.py             thin SQLite access layer
  etl.py            the extract / transform / load pipeline
  services/
    elo.py          the rating engine        (pure functions, no I/O)
    predictor.py    ratings -> probabilities (pure functions, no I/O)
    analytics.py    the analytical SQL queries
    ratings.py      queries over the rating tables
  routes/
    pages.py        HTML pages
    api.py          JSON API
  templates/        Jinja2 templates
  static/           stylesheet and Chart.js helpers
scripts/
  tune_elo.py       hyper-parameter grid search
tests/              91 tests
docs/               SRS, design, testing strategy, presentation notes
```

### Database schema

`teams` · `matches` · `goals` · `shootouts` · `tournaments` · `elo_ratings` ·
`elo_history` · `draw_calibration` · `model_metrics`

Plus a `team_matches` view that writes each match twice, once from each team's point of
view, which turns every "how did team X do" question into a single `WHERE team_id = ?`.

---

## Running it

```bash
pip install -r requirements-dev.txt
python -m app.etl      # rebuilds the database from data/raw (about 5 seconds)
python run.py          # http://127.0.0.1:8000
```

The built database is committed, so `pip install -r requirements.txt && python run.py`
is enough just to browse the site. `requirements.txt` holds only the runtime dependency
(Flask); `requirements-dev.txt` adds pandas and pytest, which are needed to rebuild the
database and run the tests but not to serve it.

Run the tests:

```bash
python -m pytest -q
```

Re-run the hyper-parameter search:

```bash
python -m scripts.tune_elo
```

---

## API

| Endpoint | Returns |
|---|---|
| `GET /api/overview` | Headline World Cup statistics |
| `GET /api/tournaments` | All 23 editions |
| `GET /api/goal-trend` | Goals per match by edition |
| `GET /api/titles` | Titles and finals per nation |
| `GET /api/goal-minutes` | Goal distribution across the 90 minutes |
| `GET /api/host-advantage` | Host vs visiting-nation records |
| `GET /api/rankings?limit=50` | Elo world rankings |
| `GET /api/teams` | Every nation that has played a World Cup |
| `GET /api/teams/<name>` | One nation's record, honours and campaigns |
| `GET /api/teams/<name>/rating-history` | That nation's rating over time |
| `GET /api/head-to-head?a=X&b=Y` | Every meeting between two nations |
| `GET /api/predict?a=X&b=Y&neutral=1` | Win / draw / loss probabilities |
| `GET /api/model` | Model metrics and the calibration table |
| `GET /api/records/scorers?limit=25` | All-time World Cup goalscorers |

```bash
curl 'http://127.0.0.1:8000/api/predict?a=Spain&b=Brazil'
```

---

## Some findings

- **Scoring collapsed after 1958.** The 1954 tournament averaged 5.38 goals a match — the
  highest ever. No edition since 1962 has reached 3.0, and the average since 1990 is 2.56.
- **Home advantage is large and real.** Nations hosting a World Cup win **61.2%** of their
  matches; visiting nations win **37.4%**.
- **Goals arrive late.** The second half produces 32% more goals than the first (1,595 vs
  1,207), and the closing 15 minutes are the single most productive window of a match.
- **Draws are a function of mismatch.** Evenly matched sides draw about twice as often as
  lopsided ones — which is exactly why the predictor needs a calibrated draw model rather
  than a fixed 25%.

---

## Data

Source: [`martj42/international_results`](https://github.com/martj42/international_results) —
a public archive of international football results.

| File | Rows | Contents |
|---|---|---|
| `results.csv` | 49,547 | Every international match, 1872–2026 |
| `goalscorers.csv` | 47,914 | Individual goals with scorer and minute |
| `shootouts.csv` | 682 | Penalty shootout results |

Verified against known results: 2018 France 4–2 Croatia (Moscow), 2022 Argentina 3–3
France won on penalties (Lusail), 2014 Germany 1–0 Argentina (Rio de Janeiro).

## Deployment

The site runs on Vercel as a single Python serverless function.

| File | Role |
|---|---|
| `api/index.py` | Entry point — exposes the Flask app as a WSGI callable |
| `vercel.json` | Rewrites every path to that function |
| `pyproject.toml` | Pins the runtime dependency tree for the function |
| `.python-version` | Pins Python 3.12 |

Two details make it work in a serverless environment:

1. **The database ships pre-built.** All the expensive work happens in the ETL at
   development time, so the function only ever reads.
2. **SQLite is opened read-only.** Serverless filesystems are read-only, so the
   connection uses `file:...?mode=ro&immutable=1`, which tells SQLite to skip locking
   and journal files rather than failing when it cannot create them.

Because the web tier needs no pandas, the deployed function installs Flask alone.

## Built with

Python · pandas · Flask · SQLite · Jinja2 · Chart.js · pytest

No ORM, no build step, no frontend framework — every layer is plain enough to read
top to bottom.
