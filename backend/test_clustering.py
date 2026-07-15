from collections import defaultdict

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.aiml.embeddings import embed_conversations
from app.aiml.clustering import cluster_conversations

source = PostgresDataSource(DB_CONFIG)

campaign_id = 1524  # First_Emi_Campaign
convos = source.get_conversations(campaign_id, days=30)

# only keep ones with real text and a real category, same filter as before
usable = [c for c in convos if c["conversation_text"] and c["top_level_category"]]
print(f"{len(usable)} usable conversations out of {len(convos)} fetched")

# group by category first — this matches our architecture: cluster WITHIN each category
by_category = defaultdict(list)
for c in usable:
    by_category[c["top_level_category"]].append(c)

for category, convo_list in by_category.items():
    print(f"\n--- Category: {category} ({len(convo_list)} conversations) ---")

    texts = [c["conversation_text"] for c in convo_list]
    vectors = embed_conversations(texts)
    labels = cluster_conversations(vectors)

    # group conversation indices by which cluster they landed in
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[label].append(idx)

    print(f"Formed {len(clusters)} clusters")
    for cluster_id, indices in clusters.items():
        print(f"  Cluster {cluster_id}: {len(indices)} conversations")
        # show a short preview of the first conversation in this cluster
        preview = convo_list[indices[0]]["conversation_text"][:120].replace("\n", " | ")
        print(f"    e.g. \"{preview}...\"")