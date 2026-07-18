import json
import sqlite3
from pathlib import Path

# Lives at Backend/results.db by default - one file, no server, no config.
# Kept completely separate from postgres_source.py (which stays read-only
# against the production DB) so there's zero risk of touching prod.
DB_PATH = Path(__file__).resolve().parent.parent.parent / "results.db"


class ResultsStore:
    """
    Local SQLite store for saved analysis results. We own this file
    outright, so writing to it is always safe - no read-only restrictions
    like the production Postgres DB.
    """

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    category TEXT,
                    from_date TEXT,
                    to_date TEXT,
                    total_conversations INTEGER,
                    usable_conversations INTEGER,
                    result_json TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def save_result(self, campaign_id: int, category: str, from_date, to_date, result: dict) -> int:
        """
        Stores the ENTIRE pipeline result (the recursive tree, sample
        conversations, everything) as one JSON blob. The tree shape changes
        run to run (different depth/branches), so there's no sane fixed
        schema to normalize it into - a JSON column is the right fit here,
        not a design shortcut.
        Returns the new row's id.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO analysis_runs
                    (campaign_id, category, from_date, to_date,
                     total_conversations, usable_conversations, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    category,
                    str(from_date),
                    str(to_date),
                    result.get("total_conversations"),
                    result.get("usable_conversations"),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            return cur.lastrowid

    def list_runs(self, campaign_id: int | None = None) -> list[dict]:
        """Lightweight list for a history view - no result_json, just metadata."""
        query = """
            SELECT id, campaign_id, category, from_date, to_date,
                   total_conversations, usable_conversations, created_at
            FROM analysis_runs
        """
        params: tuple = ()
        if campaign_id is not None:
            query += " WHERE campaign_id = ?"
            params = (campaign_id,)
        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: int) -> dict | None:
        """Full saved result for one run, including the tree."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
            ).fetchone()

        if row is None:
            return None

        data = dict(row)
        data["result"] = json.loads(data.pop("result_json"))
        return data