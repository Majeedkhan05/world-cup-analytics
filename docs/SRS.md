# Software Requirements Specification

**Project:** World Cup Analytics (Project #11 — FIFA World Cup Analytics)
**Course:** Software Engineering

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for a web-based analytics platform for
international football. The system ingests a public archive of match results, builds a
queryable database, derives a strength rating for every national team, and presents both
historical analysis and forward-looking match predictions.

### 1.2 Scope
The system covers all 23 editions of the FIFA World Cup (1930–2026) for analysis, and the
full archive of 49,547 international matches (1872–2026) for rating computation. It is a
read-only analytical system: there is no user-generated content and no authentication.

### 1.3 Definitions
| Term | Meaning |
|---|---|
| **Elo rating** | A numeric strength score updated after each match based on result vs. expectation |
| **K-factor** | How far a single result can move a rating |
| **Brier score** | Mean squared error of probabilistic forecasts; 0 is perfect, 0.667 is uninformed guessing |
| **Calibration** | Adjusting a model's probabilities to match observed frequencies |
| **Held-out set** | Data deliberately excluded from fitting, used only to measure performance |
| **ETL** | Extract, Transform, Load — the pipeline from raw files to database |

---

## 2. Overall description

### 2.1 Product perspective
A self-contained three-tier application: an offline ETL pipeline, a SQLite datastore, and a
Flask web tier serving both HTML pages and a JSON API.

### 2.2 User classes
| User | Needs |
|---|---|
| **Football follower** | Browse history, compare nations, settle arguments |
| **Analyst / journalist** | Query aggregate trends; consume the JSON API |
| **Evaluator** | Inspect the model, its assumptions, and its measured accuracy |

### 2.3 Constraints
- **C1** No paid or authenticated data sources; the dataset must be publicly reproducible.
- **C2** Widely-known technologies only, so the system is easy to read and maintain.
- **C3** Must run locally with no external services, containers, or build step.
- **C4** The full pipeline must rebuild from raw data in under one minute.

### 2.4 Assumptions
- **A1** The source archive is accurate. *(Validated against known finals — see §6.)*
- **A2** Match records are complete enough that chronological replay is meaningful.
- **A3** Team names are stable across time. *(Historical names such as "West Germany" are
  recorded as they appear in the source.)*

---

## 3. Functional requirements

### 3.1 Data pipeline
| ID | Requirement | Priority |
|---|---|---|
| FR-1 | The system shall load match, goalscorer and shootout data from CSV. | Must |
| FR-2 | The system shall discard fixtures with no recorded result. | Must |
| FR-3 | The system shall assign every nation a unique identifier. | Must |
| FR-4 | The system shall link each goal and shootout to its match. | Must |
| FR-5 | The system shall derive the champion and runner-up of each edition. | Must |
| FR-6 | The system shall correctly handle editions decided by a final round-robin rather than a single final. | Must |
| FR-7 | The system shall resolve drawn finals using the penalty shootout result. | Must |
| FR-8 | The pipeline shall be idempotent — re-running it reproduces the database exactly. | Should |

### 3.2 Rating engine
| ID | Requirement | Priority |
|---|---|---|
| FR-9 | The system shall compute an Elo rating for every nation by replaying all matches chronologically. | Must |
| FR-10 | Ratings shall be zero-sum within a match. | Must |
| FR-11 | Match importance shall scale the rating change. | Must |
| FR-12 | Winning margin shall scale the rating change, subject to a cap. | Must |
| FR-13 | Home advantage shall be applied except at neutral venues. | Must |
| FR-14 | The system shall record each nation's peak rating and the date it was reached. | Should |
| FR-15 | The system shall retain the full rating history for time-series display. | Should |

### 3.3 Prediction
| ID | Requirement | Priority |
|---|---|---|
| FR-16 | The system shall produce win / draw / loss probabilities for any two nations. | Must |
| FR-17 | The probabilities shall always form a valid distribution (non-negative, summing to 1). | Must |
| FR-18 | The draw probability shall be calibrated from observed data, not fixed. | Must |
| FR-19 | Predictions shall be based only on ratings held before the match in question. | Must |
| FR-20 | The system shall report its own accuracy against a held-out test set. | Must |
| FR-21 | The system shall explain, on screen, how each prediction was derived. | Should |

### 3.4 Analysis and presentation
| ID | Requirement | Priority |
|---|---|---|
| FR-22 | The system shall present headline World Cup statistics. | Must |
| FR-23 | The system shall list every edition with host, champion and scoring rate. | Must |
| FR-24 | The system shall show a per-nation record, honours and campaign history. | Must |
| FR-25 | The system shall rank nations by rating. | Must |
| FR-26 | The system shall report the complete head-to-head record between any two nations. | Must |
| FR-27 | The system shall present all-time scorers, biggest wins and penalty shootouts. | Should |
| FR-28 | The system shall visualise trends as charts. | Should |
| FR-29 | Every figure displayed shall also be retrievable as JSON. | Should |
| FR-30 | Unknown teams shall produce a clear "not found" response, not an error. | Must |

---

## 4. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Any page shall render in under 500 ms on a local machine. |
| NFR-2 | Performance | The ETL pipeline shall complete in under 60 seconds. |
| NFR-3 | Reliability | Invalid or missing query parameters shall produce a 400, never a crash. |
| NFR-4 | Testability | The rating and prediction logic shall be testable without a database or web server. |
| NFR-5 | Maintainability | The layers shall be strictly separated: routes contain no SQL, services contain no HTTP. |
| NFR-6 | Maintainability | All tunable constants shall live in a single configuration module. |
| NFR-7 | Usability | The interface shall work on screens down to 640 px wide. |
| NFR-8 | Transparency | The model's accuracy and limitations shall be visible in the interface, not just the documentation. |
| NFR-9 | Reproducibility | Rebuilding from raw data shall produce identical results. |
| NFR-10 | Portability | The system shall run on any machine with Python 3.9+ and no external services. |

---

## 5. Data requirements

### 5.1 Source data
| File | Rows | Fields used |
|---|---|---|
| `results.csv` | 49,547 | date, home_team, away_team, home_score, away_score, tournament, city, country, neutral |
| `goalscorers.csv` | 47,914 | date, teams, scorer, minute, own_goal, penalty |
| `shootouts.csv` | 682 | date, teams, winner |

### 5.2 Derived data
`tournaments` (edition summaries), `elo_ratings` (current and peak), `elo_history`
(99,094 rating observations), `draw_calibration` (empirical draw rates), `model_metrics`
(measured performance).

### 5.3 Quality rules
- **DQ-1** Fixtures without both scores are excluded.
- **DQ-2** Goals and shootouts that cannot be matched to a fixture are excluded.
- **DQ-3** Minutes are stored as nullable; missing values are excluded from timing analysis.
- **DQ-4** Wins + draws + losses must equal matches played for every nation. *(Tested.)*

---

## 6. Verification

| Requirement area | How it is verified |
|---|---|
| Champion derivation (FR-5, FR-6, FR-7) | Asserted against the known historical record for 1930, 1950, 2014, 2018 and 2022 |
| Rating properties (FR-10 … FR-13) | Unit tests on the pure rating functions |
| Distribution validity (FR-17) | Property tests including the extreme-mismatch case |
| Model performance (FR-20) | Held-out evaluation on 11,130 matches from 2015 onwards |
| Data quality (DQ-4) | Aggregate consistency tests against the built database |
| API contract (FR-29, FR-30, NFR-3) | Integration tests over every route |

Source accuracy was confirmed by checking three known finals against the archive:
2018 France 4–2 Croatia (Moscow), 2022 Argentina 3–3 France won on penalties (Lusail),
2014 Germany 1–0 Argentina (Rio de Janeiro).

---

## 7. Out of scope

Live or in-play data; player-level ratings beyond goalscoring; club football; betting
odds; user accounts; write operations of any kind.
