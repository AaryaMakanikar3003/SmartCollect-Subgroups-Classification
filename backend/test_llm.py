import time
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.aiml.direct_pipeline import discover_subgroups

source = PostgresDataSource(DB_CONFIG)

convos = source.get_conversations(
    campaign_id=1524,
    from_date=date(2026, 6, 15),
    to_date=date(2026, 7, 15),
    category=None,
    limit=2,   
)
usable = [c for c in convos if c["conversation_text"]]
print(f"Got {len(usable)} usable conversations")

start = time.time()
result = discover_subgroups(usable)
print(f"Took {time.time() - start:.1f}s")
print(result)