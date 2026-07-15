from sentence_transformers import SentenceTransformer

# Loaded once when this module is first imported, reused for every call.
# Loading it fresh on every request would be slow — this way it stays in memory.
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_conversations(conversation_texts: list[str]):
    """
    Takes a list of conversation text strings, returns a numpy array of
    embeddings (one vector per conversation). This is pure math, no LLM
    call involved.
    """
    if not conversation_texts:
        return []

    embeddings = _model.encode(conversation_texts, show_progress_bar=False)
    return embeddings