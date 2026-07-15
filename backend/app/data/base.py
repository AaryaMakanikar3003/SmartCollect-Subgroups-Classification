# """
# The fixed contract every data source must follow.

# Whatever the actual source is (Postgres today, something else tomorrow),
# it must promise these three things, in this order (matches the frontend flow:
# pick a bank -> pick one of its campaigns -> pick a date range):

# 1. get_banks() -> list of {"bank_id": int, "bank_name": str}
# 2. get_campaigns(bank_id) -> list of {"campaign_id": int, "campaign_name": str}
# 3. get_conversations(campaign_id, from_date, to_date) -> list of
#        {"conversation_id": int, "conversation_text": str, "top_level_category": str | None}

# Nothing outside this file should ever care HOW those are produced.
# """

# from abc import ABC, abstractmethod
# from datetime import date


# class DataSource(ABC):

#     @abstractmethod
#     def get_banks(self) -> list[dict]:
#         """Return real, non-test banks that have at least one active campaign.
#         Shape: [{"bank_id": int, "bank_name": str}, ...]
#         """
#         raise NotImplementedError

#     @abstractmethod
#     def get_campaigns(self, bank_id: int) -> list[dict]:
#         """Return active, non-trivial campaigns belonging to one bank.
#         Shape: [{"campaign_id": int, "campaign_name": str}, ...]
#         """
#         raise NotImplementedError

#     @abstractmethod
#     def get_conversations(self, campaign_id: int, from_date: date, to_date: date) -> list[dict]:
#         """Return conversations for one campaign, inclusive of both from_date and to_date.
#         Shape: [{"conversation_id": int, "conversation_text": str, "top_level_category": str | None}, ...]
#         """
#         raise NotImplementedError














"""
The fixed contract every data source must follow.

1. get_banks() -> list of {"bank_id": int, "bank_name": str}
2. get_campaigns(bank_id) -> list of {"campaign_id": int, "campaign_name": str}
3. get_category_counts(campaign_id, from_date, to_date) -> cheap counts, no JSON fetched
4. get_conversations(campaign_id, from_date, to_date, category=None, limit=None) ->
       list of {"conversation_id": int, "conversation_text": str, "top_level_category": str | None}
       category/limit filter and cap results at the SOURCE level, not in Python.

Nothing outside this file should ever care HOW those are produced.
"""

from abc import ABC, abstractmethod
from datetime import date


class DataSource(ABC):

    @abstractmethod
    def get_banks(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_campaigns(self, bank_id: int) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_category_counts(self, campaign_id: int, from_date: date, to_date: date) -> dict:
        """Fast, no-JSON-fetch counts per category. Shape:
        {"total_conversations": int, "usable_conversations": int, "categories": {"Positive": 12, ...}}
        """
        raise NotImplementedError

    @abstractmethod
    def get_conversations(
        self, campaign_id: int, from_date: date, to_date: date,
        category: str = None, limit: int = None,
    ) -> list[dict]:
        """Return conversations for one campaign/date range, optionally filtered
        to one category and capped at `limit` rows — both applied at the SQL
        level, not fetched-then-filtered in Python.
        Shape: [{"conversation_id": int, "conversation_text": str, "top_level_category": str | None}, ...]
        """
        raise NotImplementedError