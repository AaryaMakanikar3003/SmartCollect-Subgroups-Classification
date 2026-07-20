import json
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

from app.data.base import DataSource


class PostgresDataSource(DataSource):
    """
    Talks to Markytics' SmartCollect production DB (read-only access).
    This is the ONLY file that knows about BankMst / CampaignMst / VoiceBotHistory
    table names, column names, or SQL. Everything else in the pipeline
    only ever sees the DataSource contract's plain dict shape.

    Chain: BankMst.BankMstID <- CampaignMst.BankMstID
           CampaignMst.CampaignMstID <- VoiceBotHistory.CampaignMstID
    """

    def __init__(self, db_config: dict):
        self.db_config = db_config

    def _connect(self):
        return psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)

    # ---- contract method 1 ----
    def get_banks(self) -> list[dict]:
        query = """
            SELECT b."BankMstID" AS bank_id, b."BankName" AS bank_name
            FROM "BankMst" b
            JOIN "CampaignMst" c ON c."BankMstID" = b."BankMstID"
            WHERE c."IsActive" = true
              AND b."BankName" !~* 'test|demo|notworking'
            GROUP BY b."BankMstID", b."BankName"
            HAVING COUNT(DISTINCT c."CampaignMstID") > 0
            ORDER BY b."BankName";
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return [{"bank_id": r["bank_id"], "bank_name": r["bank_name"]} for r in rows]

    # ---- contract method 2 ----
    def get_campaigns(self, bank_id: int) -> list[dict]:
        query = """
            SELECT c."CampaignMstID" AS campaign_id, c."Name" AS campaign_name
            FROM "CampaignMst" c
            WHERE c."IsActive" = true AND c."BankMstID" = %s
            ORDER BY c."Name";
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (bank_id,))
                rows = cur.fetchall()
        return [{"campaign_id": r["campaign_id"], "campaign_name": r["campaign_name"]} for r in rows]

    # ---- NEW contract method: cheap counts, no JSON fetched at all ----
    def get_category_counts(self, campaign_id: int, from_date, to_date) -> dict:
        """
        Pure SQL COUNT/GROUP BY — does NOT touch Conversation_json, so this
        stays fast no matter how large the campaign is. Used to show category
        cards with counts BEFORE the user commits to processing one.

        Note: "usable" here means "has a non-empty Conclusion" — a slightly
        cheaper approximation of the old Python-side check (which also
        required the flattened conversation text to be non-empty). The two
        can differ only for rows where Conclusion is set but the JSON has
        no real dialogue (e.g. recording-link-only entries) — rare, and
        run_pipeline() still double-checks conversation_text after fetching
        the actual rows for the chosen category, so nothing wrong ever
        reaches clustering.
        """
        query = """
            SELECT v."Conclusion" AS raw_category, COUNT(*) AS cnt
            FROM "VoiceBotHistory" v
            WHERE v."CampaignMstID" = %s
              AND v."CreatedDate"::date BETWEEN %s AND %s
            GROUP BY v."Conclusion";
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (campaign_id, from_date, to_date))
                rows = cur.fetchall()

        total_conversations = sum(r["cnt"] for r in rows)
        categories = defaultdict(int)
        usable_conversations = 0
        for r in rows:
            raw = r["raw_category"]
            if raw and raw.strip():
                categories[raw.strip().title()] += r["cnt"]
                usable_conversations += r["cnt"]

        return {
            "total_conversations": total_conversations,
            "usable_conversations": usable_conversations,
            "categories": dict(categories),
        }

    # ---- contract method 3 ----
    def get_conversations(
        self, campaign_id: int, from_date, to_date, category: str = None, limit: int = None
    ) -> list[dict]:
        """
        Now filters by category and limits at the SQL level, instead of
        fetching every conversation in the date range and filtering in
        Python. This is the main fix: previously a campaign with 57k
        conversations meant pulling and JSON-parsing all 57k rows every
        run, even to get just 1000 from one category.
        """
        conditions = [
            'v."CampaignMstID" = %s',
            'v."CreatedDate"::date BETWEEN %s AND %s',
        ]
        params = [campaign_id, from_date, to_date]

        if category:
            # TRIM handles stray whitespace, ILIKE is case-insensitive —
            # together they match the same normalization (.strip().title())
            # applied to raw_category below, without needing that logic in SQL
            conditions.append('TRIM(v."Conclusion") ILIKE %s')
            params.append(category)

        query = f"""
            SELECT v."VoiceBotHistoryID" AS conversation_id,
                   v."Conversation_json" AS raw_json,
                   v."Conclusion" AS top_level_category
            FROM "VoiceBotHistory" v
            WHERE {' AND '.join(conditions)}
            ORDER BY v."CreatedDate" DESC
        """
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        conversations = []
        for r in rows:
            raw_category = r["top_level_category"]
            conversations.append({
                "conversation_id": r["conversation_id"],
                "conversation_text": self._flatten_conversation(r["raw_json"]),
                "top_level_category": raw_category.strip().title() if raw_category else None,
            })
        return conversations

    # ---- helper: internal only, not part of the contract ----
    def _flatten_conversation(self, raw_json) -> str:
        if raw_json is None:
            return ""
        if isinstance(raw_json, str):
            try:
                raw_json = json.loads(raw_json)
            except (json.JSONDecodeError, TypeError):
                return ""
        if not isinstance(raw_json, dict):
            return ""
        turns = raw_json.get("conversation")
        if not isinstance(turns, list):
            return ""
        lines = []
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            message = turn.get("message")
            if not message:
                continue
            sender = turn.get("sender") or turn.get("type") or "unknown"
            lines.append(f"{sender}: {message}")
        return "\n".join(lines)