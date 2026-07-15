from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.aiml.embeddings import embed_conversations

source = PostgresDataSource(DB_CONFIG)

# reuse the same campaign we already know has data
campaign_id = 1524  # First_Emi_Campaign
convos = source.get_conversations(campaign_id, days=30)

print(f"Fetched {len(convos)} conversations")

# only embed the ones that actually have text and a real category
texts = [c["conversation_text"] for c in convos if c["conversation_text"] and c["top_level_category"]]
print(f"{len(texts)} have both text and a category")

if texts:
    print("\nEmbedding a small sample (first 5)...")
    sample = texts[:5]
    vectors = embed_conversations(sample)
    print(f"Got {len(vectors)} vectors, each of length {len(vectors[0])}")
    print("First vector preview (first 10 numbers):", vectors[0][:10])
else:
    print("No usable conversations found — try a bigger `days` value or a different campaign_id")