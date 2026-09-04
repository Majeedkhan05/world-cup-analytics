"""Shared pytest fixtures."""
import pandas as pd
import pytest

from app import create_app
from app.config import DB_PATH


@pytest.fixture(scope="session")
def app():
    if not DB_PATH.exists():
        pytest.skip("database not built - run `python -m app.etl` first")
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def ctx(app):
    """An application context, so the service layer can reach the database."""
    with app.app_context():
        yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_matches():
    """A tiny hand-made fixture used by the ETL tests."""
    return pd.DataFrame([
        # a group stage plus a final round-robin sharing the same last date
        ("1950-06-24", "Brazil", "Mexico", 4, 0),
        ("1950-06-25", "Uruguay", "Bolivia", 8, 0),
        ("1950-07-09", "Brazil", "Spain", 6, 1),
        ("1950-07-09", "Uruguay", "Sweden", 3, 2),
        ("1950-07-16", "Sweden", "Spain", 3, 1),
        ("1950-07-16", "Uruguay", "Brazil", 2, 1),
    ], columns=["date", "home_team", "away_team", "home_score", "away_score"])
