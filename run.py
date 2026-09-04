"""Development entry point.

    python run.py            # http://127.0.0.1:8000
    PORT=5050 python run.py  # pick a different port
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8000)))
