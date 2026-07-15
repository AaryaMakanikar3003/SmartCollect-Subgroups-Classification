from sklearn.cluster import KMeans
import numpy as np


def cluster_conversations(embeddings, n_clusters: int = None):
    """
    Groups embeddings into clusters. Returns a list of cluster labels,
    one per input embedding, e.g. [0, 2, 1, 0, 0, 2, ...]

    If n_clusters isn't given, picks a reasonable number based on how
    much data there is, so this works whether we have 20 conversations
    or 2000.
    """
    embeddings = np.array(embeddings)
    n_samples = len(embeddings)

    if n_samples < 2:
        # not enough data to cluster at all
        return [0] * n_samples

    if n_clusters is None:
        # rough heuristic: roughly one cluster per 15-20 conversations,
        # bounded between 2 and 8 so it never gets silly on either end
        n_clusters = max(2, min(8, n_samples // 15))

    n_clusters = min(n_clusters, n_samples)  # can't have more clusters than data points

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    return labels.tolist()