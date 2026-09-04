"""Grid-search the Elo hyper-parameters against held-out matches.

The rating engine has three knobs: the K-factor (how fast ratings move), the
home-advantage bonus, and how much a big winning margin counts. Rather than
guessing them, this script sweeps sensible values, re-runs the whole history for
each combination and scores it on matches the model never learned from.

Run with:  python -m scripts.tune_elo
"""
import itertools

import pandas as pd

from app import config
from app.etl import extract, clean_matches, calibrate_draw_model, score, HOLDOUT_FROM
from app.services.elo import EloEngine

K_VALUES = [10, 15, 20, 25, 30, 40]
HOME_VALUES = [0, 40, 65, 90]
MARGIN_CAPS = [1.0, 1.5, 2.0, 3.0]


def evaluate(matches, k, home, cap):
    """Replay history with these settings and score the predictor."""
    config.ELO_K_BASE = k
    config.ELO_HOME_ADVANTAGE = home
    config.ELO_MARGIN_CAP = cap

    import app.services.elo as elo
    elo.ELO_K_BASE, elo.ELO_HOME_ADVANTAGE, elo.ELO_MARGIN_CAP = k, home, cap

    engine = EloEngine().run(matches.to_dict("records"))
    pre = matches["id"].map(engine.pre_match)
    df = matches.copy()
    df["home_elo"] = [p[0] for p in pre]
    df["away_elo"] = [p[1] for p in pre]

    train = df[df["date"] < HOLDOUT_FROM]
    test = df[df["date"] >= HOLDOUT_FROM]
    cal = calibrate_draw_model(train)
    result = score(test, dict(zip(cal["bucket"], cal["draw_rate"])))
    spread = df["home_elo"].max() - df["home_elo"].min()
    return {"k": k, "home": home, "margin_cap": cap,
            "accuracy": result["accuracy"], "brier": result["brier_score"],
            "rating_spread": round(spread)}


def main():
    results, _, _ = extract()
    matches = clean_matches(results)

    rows = []
    combos = list(itertools.product(K_VALUES, HOME_VALUES, MARGIN_CAPS))
    for i, (k, home, cap) in enumerate(combos, 1):
        rows.append(evaluate(matches, k, home, cap))
        print(f"  [{i:>3}/{len(combos)}] K={k:<3} home={home:<3} cap={cap:<4} "
              f"acc={rows[-1]['accuracy']:.4f} brier={rows[-1]['brier']:.4f}")

    df = pd.DataFrame(rows).sort_values("brier")
    print("\nBest 10 by Brier score (lower is better):")
    print(df.head(10).to_string(index=False))
    return df


if __name__ == "__main__":
    main()
