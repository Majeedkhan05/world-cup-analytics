# Presentation & Viva Notes

Everything you need to present this project and answer questions about it.

---

## 1. The one-sentence description

> "I built an analytics platform over 49,547 real international football matches from 1872
> to 2026. It analyses every World Cup, ranks all 337 national teams with an Elo rating
> engine I implemented, and predicts match outcomes at 60% accuracy against a held-out
> test set."

---

## 2. Suggested 10-minute structure

| Time | Section | What to show |
|---|---|---|
| 0:00–1:00 | Problem & data | The dataset, and that you verified it against known finals |
| 1:00–2:30 | Architecture | The layer diagram from `docs/DESIGN.md` |
| 2:30–4:00 | ETL pipeline | Run `python -m app.etl` live — it takes 5 seconds |
| 4:00–6:30 | The Elo model | The three formulas; this is the heart of the talk |
| 6:30–8:00 | Live demo | Dashboard → team page → predictor |
| 8:00–9:00 | Testing & evaluation | 91 tests, and the held-out 60.1% |
| 9:00–10:00 | Limitations & extensions | Show you know where it stops |

**Open with the running application, not with slides.** Have `python run.py` already going.

---

## 3. The four things to explain well

### 3.1 The architecture (why it is layered)

> "It's a three-tier layered architecture. The ETL pipeline is offline — it does the
> expensive work once. The service layer holds all the analysis. The route layer only
> gathers and renders.
>
> The rule I enforced is that **routes contain no SQL and services contain no HTTP**. That's
> not decoration — it's what makes the project testable. My Elo engine takes numbers and
> returns numbers, so I can test the most important logic without a database or a web
> server at all."

### 3.2 The Elo formula

Draw this on the board:

```
E = 1 / (1 + 10^(-(R_a - R_b) / 400))
R_a' = R_a + K x weight x margin x (S - E)
```

> "E is what the ratings expected. S is what happened — 1, 0.5 or 0. The rating moves by the
> **difference between them**. So a team gains points only by doing better than expected.
> Beat a much stronger side and you gain a lot; beat a much weaker one and you gain almost
> nothing. It's zero-sum: whatever the winner gains, the loser loses.
>
> The 400 is what defines Elo — a 400-point gap means the stronger team is expected to take
> ten times as many points. I have a unit test asserting exactly that property."

### 3.3 Turning one number into three probabilities

This is the question most likely to be asked, so have the answer ready:

> "Elo gives one number, E, which blends wins and draws. To get three probabilities I need
> to know how often draws happen — and rather than assume a fixed 25%, I **measured it**.
>
> Because I stored each team's rating as it stood before every match, I could bucket all
> 49,000 matches by the rating gap at kick-off and count the real draw rate in each bucket.
> It turns out evenly matched teams draw about 28% of the time and badly mismatched ones
> about 12%.
>
> Then, since E = P(win) + half of P(draw), the algebra gives me the other two."

### 3.4 Honest evaluation

> "I calibrated the draw model on matches before 2015 only, then scored it on the 11,130
> matches played since — data the model never saw. It gets 60.1% right, against 47.7% for
> just always picking the home team.
>
> Crucially, every prediction only uses ratings from before that match, so it's a
> walk-forward evaluation, not hindsight. And I show both numbers **inside the app**, so
> anyone using it can see how much to trust it."

---

## 4. Live demo script

```bash
python -m app.etl     # 5 seconds — show the pipeline actually running
python run.py
```

1. **Dashboard.** Point at the goals-per-match chart: *"1954 averaged 5.38 goals a match.
   No tournament since 1962 has reached 3.0."* Then host advantage: *"Hosts win 61%,
   visitors 37% — that's why the model has a home-advantage term."*
2. **A team page** (try Argentina). *"This is 1,077 matches replayed through the rating
   engine. You can see the peak on the day they won in 2022."*
3. **The predictor.** Pick Spain vs Brazil. *"And here's the panel that shows exactly how
   that number was produced, plus the model's own accuracy."*
4. **The API.** `curl 'http://127.0.0.1:8000/api/predict?a=Spain&b=Brazil'` — *"every figure
   on the site is also machine-readable."*
5. **The tests.** `python -m pytest -q` → 91 passed in ~2 seconds.

---

## 5. Likely questions, with answers

**"Why SQLite and not MySQL or Postgres?"**
> The dataset is 13 MB and single-user. SQLite ships with Python, needs no server, and the
> whole database is one file I can commit. A server would add operational cost for zero
> benefit. If this became multi-user with concurrent writes, Postgres would be the move.

**"Why no ORM?"**
> Because in this project the queries *are* the analysis. An ORM would hide the most
> interesting code behind generated SQL. It also means one less dependency and nothing
> magic to explain.

**"Where did the K-factor and home advantage come from?"**
> Not from guessing — `scripts/tune_elo.py` grid-searches 96 combinations, replays the full
> history for each, and scores them on held-out matches. My first hand-picked value gave a
> 300-point gap between Spain and Brazil and wildly overconfident forecasts. The search
> found settings with a better Brier score *and* more believable ratings.

**"Is 60% accuracy good?"**
> For three-way football outcomes, yes. The baseline is 47.7%, and professional models sit
> in the mid-to-high 50s. Football is genuinely low-scoring and high-variance — that's why
> upsets happen. A model claiming 90% would be a model with a bug.

**"What's a Brier score?"**
> The mean squared error of the probabilities. If I say 70% and it happens, I'm penalised
> 0.09; if I say 70% and it doesn't, I'm penalised 0.49. It rewards being confident *and*
> right, and punishes confident and wrong. Uninformed guessing scores 0.667; mine is 0.516.

**"How do you know the data is correct?"**
> I checked known results against the archive before building anything: 2018 France 4–2
> Croatia in Moscow, 2022 Argentina drew 3–3 with France and won on penalties in Lusail,
> 2014 Germany 1–0 Argentina in Rio. The all-time scorer list also matches the record —
> Klose 16, Ronaldo 15, Müller 14, Fontaine 13, Pelé 12.

**"What was the hardest bug?"**
> Deriving the champion of each tournament. I took "the winner of the last match played",
> which works for 22 of the 23 editions — but 1950 had no final. It ended in a four-team
> round-robin whose last two matches were on the same day, so my code crowned Sweden
> instead of Uruguay. I added a tie-break that picks the fixture between the two strongest
> teams, and wrote a regression test that asserts 1950 → Uruguay so it can't come back.

**"What would you add with more time?"**
> Three things. Match-stage labels, so I could separate group from knockout football.
> Era-adjusted ratings, since a 2000-rating today isn't comparable to one in 1950. And a
> tournament simulator — run the bracket 10,000 times through the model to get each team's
> probability of winning the whole thing.

**"Is this your own work? Where did the model come from?"**
> Elo is a published rating system from chess, adapted here for football. The
> implementation, the tournament weighting, the margin cap, the calibrated draw model, the
> hyper-parameter search and the evaluation methodology are all mine — that's
> `app/services/elo.py`, `predictor.py` and `scripts/tune_elo.py`, about 200 lines.

---

## 6. Numbers worth memorising

| | |
|---|---|
| Matches in the database | 49,547 (1872–2026) |
| World Cup matches / editions | 1,068 across 23 |
| Nations rated / World Cup nations | 337 / 86 |
| Goals per World Cup match | 2.84 |
| Held-out accuracy vs baseline | 60.1% vs 47.7% |
| Brier score | 0.516 (guessing = 0.667) |
| Test-set size | 11,130 matches |
| Tests | 91, passing in ~2 s |
| ETL runtime | about 5 seconds |
| Highest-scoring edition | 1954, at 5.38 goals per match |
| Host win rate vs visitors | 61.2% vs 37.4% |

---

## 7. Be ready to admit the limits

Volunteering these makes you look stronger, not weaker:

- Elo uses **only results** — no squads, injuries, or rest. That is the real accuracy ceiling.
- **West Germany and Germany are separate entities**, as the source records them.
- The source has **no match-stage labels**, so group and knockout football can't be split.
- The draw calibration is **global**, not per-era, though draw rates have drifted since 1872.
