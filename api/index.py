"""Vercel serverless entry point.

Vercel routes every request to this module and looks for a WSGI callable
named `app`. Locally the same application is started by run.py instead.
"""
import os
import sys
from pathlib import Path

# The function runs with the repository root as the working directory, but the
# root is not on sys.path by default.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402

# Serverless filesystems are read-only, so the database is opened read-only.
app = create_app(read_only=bool(os.environ.get("VERCEL")))
