import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI, APIConnectionError, APIError

# Mrakytics LLM Gateway is OpenAI-compatible.
_MODEL = os.getenv("MRAKYTICS_LLM_MODEL", "google/gemma-4-E4B-it")

_client = None
_client_lock = threading.Lock()


class RateLimiter:
    """
    Enforces a minimum gap between consecutive LLM requests, across ALL
    threads. Complements (doesn't replace) the concurrency semaphore -
    the semaphore caps how many requests run at once, this caps how
    fast new ones can start, so we never fire faster than the gateway
    can actually keep up with.
    """
    def __init__(self, min_interval: float = 0.5):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._next_allowed_time = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            if now < self._next_allowed_time:
                sleep_for = self._next_allowed_time - now
            else:
                sleep_for = 0.0
            self._next_allowed_time = max(now, self._next_allowed_time) + self.min_interval
        if sleep_for > 0:
            time.sleep(sleep_for)


_rate_limiter = RateLimiter(min_interval=0.5)


def _get_client() -> OpenAI:
    global _client

    with _client_lock:
        if _client is None:
            api_key = os.getenv("MRAKYTICS_LLM_API_KEY") 
            base_url = os.getenv("MRAKYTICS_LLM_BASE_URL")

            if not api_key:
                raise RuntimeError(
                    "MRAKYTICS_LLM_API_KEY not set. Add it to your .env file."
                )

            if not base_url:
                raise RuntimeError(
                    "MRAKYTICS_LLM_BASE_URL not set. Example: http://<host>:8100/v1"
                )

            _client = OpenAI(api_key=api_key, base_url=base_url, timeout=600.0)
            print(f"    [naming] using Mrakytics LLM Gateway model: {_MODEL}")

    return _client


# def _call_llm(prompt: str, max_tokens: int, retries: int = 3, semaphore=None):
#     client = _get_client()
#     last_error = None

#     for attempt in range(1, retries + 1):
#         if semaphore:
#             semaphore.acquire()
#         try:
#             print(f"    [naming] sending request (attempt {attempt}, max_tokens={max_tokens})...")
#             start = time.time()
#             result = client.chat.completions.create(
#                 model=_MODEL,
#                 max_tokens=max_tokens,
#                 messages=[{"role": "user", "content": prompt}],
#                 timeout=600.0,
#             )
#             print(f"    [naming] got response in {time.time() - start:.1f}s")
#             return result
#         except (APIConnectionError, APIError) as e:
#             last_error = e
#             wait = attempt * 2
#             print(repr(e))
#             time.sleep(wait)
#         finally:
#             if semaphore:
#                 semaphore.release()

#     raise last_error
def _call_llm(prompt: str, max_tokens: int, retries: int = 3, semaphore=None):
    client = _get_client()
    last_error = None

    for attempt in range(1, retries + 1):
        if semaphore:
            semaphore.acquire()
        try:
            _rate_limiter.wait()   # <-- enforces the 0.5s spacing here
            print(f"    [naming] sending request (attempt {attempt}, max_tokens={max_tokens})...")
            start = time.time()
            result = client.chat.completions.create(
                model=_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=600.0,
            )
            print(f"    [naming] got response in {time.time() - start:.1f}s")
            return result
        except (APIConnectionError, APIError) as e:
            last_error = e
            wait = attempt * 2
            print(repr(e))
            time.sleep(wait)
        finally:
            if semaphore:
                semaphore.release()

    raise last_error


def name_cluster(sample_texts: list[str], category: str, sample_size: int = 8) -> dict:
    """
    Takes sample conversations from one cluster and asks the LLM to propose
    a short cluster name plus a one-line description.

    Returns: {"name": str, "description": str}
    """
    if not sample_texts:
        return {
            "name": "Empty cluster",
            "description": "No conversations in this cluster.",
        }

    sample = sample_texts[:sample_size]

    convo_block = "\n\n".join(
        f"--- Conversation {i + 1} ---\n{text[:1500]}"
        for i, text in enumerate(sample)
    )

    prompt = f"""You are looking at debt-collection voicebot call transcripts (Hinglish, EMI recovery calls).
All of these calls were already tagged with the outcome category "{category}".
Within that category, these specific calls were grouped together by an algorithm
because they are similar to each other in content.

Read the {len(sample)} sample conversations below and figure out what makes this
specific subgroup distinct from other calls in the same "{category}" category,
for example what the customer said, how they responded, or how the call ended.

Respond with ONLY a valid JSON object, no markdown, no extra text.
Use exactly these two keys:
{{"name": "2-4 word cluster name", "description": "one sentence describing what happens in these calls"}}

{convo_block}"""

    response = _call_llm(prompt, max_tokens=300)

    choice = response.choices[0]
    raw = (choice.message.content or "").strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.removeprefix("json").strip()

    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if not parsed:
        print(
            f"    [naming] empty/unparseable response - "
            f"finish_reason={choice.finish_reason!r}, raw={raw[:100]!r}"
        )

        if sample_size > 4:
            return name_cluster(sample_texts, category, sample_size=4)

    if parsed:
        name = parsed.get("name")
        description = parsed.get("description", "")

        if not name:
            words = description.strip().split()
            name = " ".join(words[:4]).rstrip(",.") if words else "Unnamed cluster"

        return {"name": name, "description": description}

    return {"name": "Unnamed cluster", "description": raw[:200]}


def name_all_clusters(
    convo_list: list[dict],
    labels: list[int],
    category: str,
    max_workers: int = 6,
) -> dict[int, dict]:
    """
    Names all clusters for a category.

    max_workers controls how many LLM calls run in parallel. Keep this lower
    for the Mrakytics gateway at first, then increase if it handles the load.
    """
    from collections import defaultdict

    clusters = defaultdict(list)

    for idx, label in enumerate(labels):
        clusters[label].append(convo_list[idx])

    named = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_cluster = {
            executor.submit(
                name_cluster,
                [c["conversation_text"] for c in conversations],
                category,
            ): (cluster_id, conversations)
            for cluster_id, conversations in clusters.items()
        }

        for future in as_completed(future_to_cluster):
            cluster_id, conversations = future_to_cluster[future]

            result = future.result()

            named[cluster_id] = {
                **result,
                "count": len(conversations),
                "examples": [
                    {
                        "conversation_id": c["conversation_id"],
                        "conversation_text": c["conversation_text"],
                    }
                    for c in conversations[:8]
                ],
            }

    return named