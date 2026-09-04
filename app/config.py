"""Application configuration (single source of truth for paths and tunables)."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "worldcup.sqlite3"

# --- Elo engine tunables -------------------------------------------------
# These three values were not guessed: scripts/tune_elo.py sweeps them over a
# grid, replays the whole match history for each combination, and scores it on
# matches from 2015 onwards that the model never learned from. The settings
# below were the best of 96 combinations (Brier 0.516, accuracy 60.1%).
ELO_START = 1500.0      # every nation starts here on its first ever match
ELO_HOME_ADVANTAGE = 65  # rating points added to the host/home side
ELO_K_BASE = 25          # base K-factor (how fast ratings move)
ELO_MARGIN_CAP = 3.0     # ceiling on the big-win multiplier

# Tournament weights: a World Cup result should move a rating far more than
# a friendly. Multiplies the K-factor.
ELO_WEIGHTS = {
    "FIFA World Cup": 2.0,
    "FIFA World Cup qualification": 1.4,
    "UEFA Euro": 1.6,
    "Copa América": 1.6,
    "African Cup of Nations": 1.5,
    "AFC Asian Cup": 1.5,
    "Confederations Cup": 1.4,
    "UEFA Nations League": 1.3,
    "Friendly": 0.7,
}
ELO_WEIGHT_DEFAULT = 1.0

WORLD_CUP = "FIFA World Cup"
