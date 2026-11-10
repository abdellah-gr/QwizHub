import sqlite3
from datetime import datetime


"""
Lightweight sqlite3 wrapper that provides a simple `db.execute(sql, *params)`
interface. Returns a list of dicts for SELECT, the new row id for INSERT, and
the number of affected rows for UPDATE/DELETE. Raises ValueError on constraint
violations.

Note: this file was generated with AI assistance (Claude, by Anthropic).
The application originally used a different SQL helper library, and this
wrapper replaces it so the project only depends on Python's standard sqlite3.
"""


class DB:
    def __init__(self, path):
        self.path = path

    def execute(self, sql, *params):
        # Convert datetime objects to strings
        params = tuple(
            p.strftime("%Y-%m-%d %H:%M:%S") if isinstance(p, datetime) else p
            for p in params
        )

        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            cur = conn.execute(sql, params)
            verb = sql.lstrip().split(None, 1)[0].upper()

            if verb == "SELECT":
                return [dict(row) for row in cur.fetchall()]

            result = cur.lastrowid if verb == "INSERT" else cur.rowcount
            conn.commit()
            return result

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(str(e)) from e
        finally:
            conn.close()
