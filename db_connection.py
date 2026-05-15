# db_connection.py
# Purpose: provide a reusable SQLite connection for query functions.

import os
import sqlite3


DB_PATH = os.path.join(os.path.dirname(__file__), "data", "immunisation.db")


def get_connection():
    """Return a SQLite connection with Row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
