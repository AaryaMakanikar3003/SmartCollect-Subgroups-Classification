# from collections import defaultdict

# from app.aiml.embeddings import embed_conversations
# from app.aiml.clustering import cluster_conversations
# from app.aiml.naming import name_all_clusters

# MIN_CONVOS_TO_CLUSTER = 15


# def get_category_counts(source, campaign_id: int, from_date, to_date) -> dict:
#     """
#     Fast, no-AI step: fetch conversations for a campaign + date range and
#     return how many fall into each category. Used to show the user category
#     cards with counts BEFORE they commit to running clustering on any of them.

#     Returns:
#     {
#       "total_conversations": 4633,
#       "usable_conversations": 4420,
#       "categories": {"Positive": 1200, "Negative": 340, "Neutral": 2880}
#     }
#     """
#     convos = source.get_conversations(campaign_id, from_date, to_date)
#     usable = [c for c in convos if c["conversation_text"] and c["top_level_category"]]

#     counts = defaultdict(int)
#     for c in usable:
#         counts[c["top_level_category"]] += 1

#     return {
#         "total_conversations": len(convos),
#         "usable_conversations": len(usable),
#         "categories": dict(counts),
#     }


# def run_pipeline(
#     source,
#     campaign_id: int,
#     from_date,
#     to_date,
#     category: str,
#     limit: int | None = None,
#     on_progress=None,
# ):
#     """
#     Runs the subgroup discovery pipeline for ONE category within one
#     campaign + date range (not all categories anymore — the user picks
#     a category up front, after seeing counts from get_category_counts()).

#     limit: if given, only cluster the first `limit` conversations in that
#     category (used when the user declines to process the full count).

#     on_progress: optional callback, called with a short status string at
#     each stage, so the caller (WebSocket handler) can push live updates.

#     Returns a plain dict result, e.g.:
#     {
#       "campaign_id": 1524,
#       "from_date": "2026-06-01",
#       "to_date": "2026-07-01",
#       "category": "Positive",
#       "total_in_category": 1200,
#       "processed_count": 1000,
#       "clusters": [
#         {"name": "...", "description": "...", "count": 210},
#         ...
#       ]
#     }
#     """
#     def notify(msg):
#         if on_progress:
#             on_progress(msg)
#         print(f"[pipeline] {msg}")

#     notify("Fetching conversations...")
#     convos = source.get_conversations(campaign_id, from_date, to_date)
#     usable = [c for c in convos if c["conversation_text"] and c["top_level_category"]]

#     convo_list = [c for c in usable if c["top_level_category"] == category]
#     total_in_category = len(convo_list)

#     if limit is not None:
#         convo_list = convo_list[:limit]

#     result = {
#         "campaign_id": campaign_id,
#         "from_date": str(from_date),
#         "to_date": str(to_date),
#         "category": category,
#         "total_in_category": total_in_category,
#         "processed_count": len(convo_list),
#     }

#     if len(convo_list) < MIN_CONVOS_TO_CLUSTER:
#         result["skipped_reason"] = (
#             f"Fewer than {MIN_CONVOS_TO_CLUSTER} conversations, not enough to cluster meaningfully"
#         )
#         result["clusters"] = []
#         notify("Done.")
#         return result

#     notify(f"Embedding {len(convo_list)} conversations in '{category}'...")
#     texts = [c["conversation_text"] for c in convo_list]
#     vectors = embed_conversations(texts)

#     notify(f"Clustering '{category}'...")
#     labels = cluster_conversations(vectors)

#     notify(f"Naming clusters for '{category}'...")
#     named = name_all_clusters(convo_list, labels, category)

#     result["clusters"] = [
#         {"name": info["name"], "description": info["description"], "count": info["count"]}
#         for info in sorted(named.values(), key=lambda x: -x["count"])
#     ]

#     notify("Done.")
#     return result












from app.aiml.embeddings import embed_conversations
from app.aiml.clustering import cluster_conversations
from app.aiml.naming import name_all_clusters

MIN_CONVOS_TO_CLUSTER = 15


def get_category_counts(source, campaign_id: int, from_date, to_date) -> dict:
    """Thin wrapper — delegates straight to the SQL-level count, no Python fetch."""
    return source.get_category_counts(campaign_id, from_date, to_date)


def run_pipeline(
    source,
    campaign_id: int,
    from_date,
    to_date,
    category: str,
    limit: int | None = None,
    on_progress=None,
):
    def notify(msg):
        if on_progress:
            on_progress(msg)
        print(f"[pipeline] {msg}")

    notify("Checking category size...")
    counts = source.get_category_counts(campaign_id, from_date, to_date)
    total_in_category = counts["categories"].get(category, 0)

    notify("Fetching conversations...")
    convo_list = source.get_conversations(
        campaign_id, from_date, to_date, category=category, limit=limit
    )
    convo_list = [c for c in convo_list if c["conversation_text"]]

    result = {
        "campaign_id": campaign_id,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "category": category,
        "total_in_category": total_in_category,
        "processed_count": len(convo_list),
    }

    if len(convo_list) < MIN_CONVOS_TO_CLUSTER:
        result["skipped_reason"] = (
            f"Fewer than {MIN_CONVOS_TO_CLUSTER} conversations, not enough to cluster meaningfully"
        )
        result["clusters"] = []
        notify("Done.")
        return result

    notify(f"Embedding {len(convo_list)} conversations in '{category}'...")
    texts = [c["conversation_text"] for c in convo_list]
    vectors = embed_conversations(texts)

    notify(f"Clustering '{category}'...")
    labels = cluster_conversations(vectors)

    notify(f"Naming clusters for '{category}'...")
    named = name_all_clusters(convo_list, labels, category)

    result["clusters"] = [
        {
            "name": info["name"],
            "description": info["description"],
            "count": info["count"],
            "examples": info["examples"],
        }
        for info in sorted(named.values(), key=lambda x: -x["count"])
    ]

    notify("Done.")
    return result