"""
Quick manual sanity check for the full bank -> campaign -> conversations chain.

    python test_data_source.py
"""

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource

source = PostgresDataSource(DB_CONFIG)

print("Step 1: Fetching banks...")
banks = source.get_banks()
print(f"Got {len(banks)} banks. First 5:")
for b in banks[:5]:
    print(" ", b)

# use Vedika Finance as the test bank if present, else just the first one
test_bank = next((b for b in banks if b["bank_name"] == "Vedika Finance"), banks[0])
print(f"\nStep 2: Fetching campaigns for bank: {test_bank['bank_name']}")
campaigns = source.get_campaigns(test_bank["bank_id"])
print(f"Got {len(campaigns)} campaigns. First 5:")
for c in campaigns[:5]:
    print(" ", c)

if campaigns:
    test_campaign = next(
        (c for c in campaigns if c["campaign_name"] == "Default OverDue Flow with Whatsapp"),
        campaigns[0],
    )
    print(f"\nStep 3: Fetching last 7 days of conversations for campaign: {test_campaign['campaign_name']}")
    convos = source.get_conversations(test_campaign["campaign_id"], days=7)
    print(f"Got {len(convos)} conversations. First one:")
    if convos:
        print(" conversation_id:", convos[0]["conversation_id"])
        print(" top_level_category:", convos[0]["top_level_category"])
        print(" conversation_text preview:", convos[0]["conversation_text"][:200])
    else:
        print(" No conversations in this window for this campaign. Try a bigger `days` value or a different campaign.")
