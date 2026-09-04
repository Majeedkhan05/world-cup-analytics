"""Flask application factory."""
from flask import Flask

from app.config import DB_PATH
from app import db


def create_app(db_path=DB_PATH):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    app.config["JSON_SORT_KEYS"] = False

    app.teardown_appcontext(db.close_db)

    from app.routes.pages import bp as pages_bp
    from app.routes.api import bp as api_bp
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    return app
