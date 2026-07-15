from collections import defaultdict

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.aiml.embeddings import embed_conversations
from app.aiml.clustering import cluster_conversations
from app.aiml.naming import name_all_clusters

source = PostgresDataSource(DB_CONFIG)

campaign_id = 1524  # First_Emi_Campaign
convos = source.get_conversations(campaign_id, days=30)

usable = [c for c in convos if c["conversation_text"] and c["top_level_category"]]
print(f"{len(usable)} usable conversations out of {len(convos)} fetched")

by_category = defaultdict(list)
for c in usable:
    by_category[c["top_level_category"]].append(c)

# quick skip rule for tiny categories, per yesterday's data-quality note —
# not enough data to form a meaningful cluster below this
MIN_CONVOS_TO_CLUSTER = 15

for category, convo_list in by_category.items():
    print(f"\n--- Category: {category} ({len(convo_list)} conversations) ---")

    if len(convo_list) < MIN_CONVOS_TO_CLUSTER:
        print(f"  Skipped — fewer than {MIN_CONVOS_TO_CLUSTER} conversations, not enough to cluster meaningfully")
        continue

    texts = [c["conversation_text"] for c in convo_list]
    vectors = embed_conversations(texts)
    labels = cluster_conversations(vectors)

    print(f"Formed {len(set(labels))} clusters, naming each...")
    named = name_all_clusters(convo_list, labels, category)

    for cluster_id, info in sorted(named.items(), key=lambda x: -x[1]["count"]):
        print(f"  Cluster {cluster_id} ({info['count']} conversations): \"{info['name']}\"")
        print(f"    {info['description']}")