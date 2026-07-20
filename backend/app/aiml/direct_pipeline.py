# import json
# import re
# import threading
# from collections import defaultdict
# from concurrent.futures import ThreadPoolExecutor, as_completed

# from app.aiml.naming import _call_llm

# # Hard cap on concurrent LLM requests across the WHOLE pipeline, no matter how
# # many threads end up queued (batch-level parallelism + sibling-branch
# # parallelism together). Tune this to whatever your gateway can actually
# # handle concurrently - raising it doesn't change any analysis output, only
# # how many requests can be in flight at once.
# _MAX_CONCURRENT_LLM_CALLS = 2
# _llm_semaphore = threading.Semaphore(_MAX_CONCURRENT_LLM_CALLS)


# # def _call_llm_guarded(prompt: str, max_tokens: int):
# #     with _llm_semaphore:
# #         return _call_llm(prompt, max_tokens=max_tokens)
# # direct_pipeline.py
# def _call_llm_guarded(prompt: str, max_tokens: int):
#     return _call_llm(prompt, max_tokens=max_tokens, semaphore=_llm_semaphore)


# def _extract_json(raw: str) -> str:
#     cleaned = raw.strip()
#     cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
#     cleaned = re.sub(r"\s*```$", "", cleaned)
#     return cleaned.strip()


# def _safe_parse_list(raw: str, caller: str) -> list[dict]:
#     try:
#         parsed = json.loads(_extract_json(raw))
#     except Exception:
#         print(f"    [{caller}] failed to parse, raw={raw!r}")
#         return []

#     if isinstance(parsed, dict):
#         parsed = [parsed]

#     if not isinstance(parsed, list):
#         print(f"    [{caller}] parsed JSON was not a list or object, raw={raw!r}")
#         return []

#     return [item for item in parsed if isinstance(item, dict)]


# def _chunks(lst: list, n: int) -> list[list]:
#     return [lst[i:i + n] for i in range(0, len(lst), n)]


# CATEGORY_MEANINGS = {
#     "positive": "the bot got what it wanted - a CLEAR, CERTAIN commitment such as a specific payment date or timeframe.",
#     "negative": "the customer did not engage meaningfully - no reply, stayed silent, or the call had no real conversation.",
#     "neutral": "the customer responded but was UNCLEAR or NON-COMMITTAL - no date or timeframe given with certainty.",
# }


# def _format_context(context_path: list[tuple[str, str]]) -> str:
#     """
#     context_path is the chain of decisions already made above this node,
#     e.g. [("category", "Positive"), ("subgroup", "Promise to Pay")].
#     This is what stops the LLM from re-discovering the parent as a child,
#     and lets it condition on what's already known.
#     """
#     if not context_path:
#         return "This is the top level - no parent grouping has been decided yet."

#     lines = []
#     for level, name in context_path:
#         if level == "category":
#             meaning = CATEGORY_MEANINGS.get(name.strip().lower())
#             lines.append(f'- top-level category: "{name}"' + (f" ({meaning})" if meaning else ""))
#         else:
#             lines.append(f'- {level}: "{name}"')

#     return "These conversations already belong to:\n" + "\n".join(lines)


# # ------------------------------------------------------------------
# # STAGE 1a - free discovery. No fixed template: the LLM looks at one
# # small batch and names whatever patterns are actually there.
# # ------------------------------------------------------------------
# def _propose_labels(batch: list[dict], context_path: list[tuple[str, str]],
#                      min_labels: int = 1, max_labels: int = 6) -> list[dict]:
#     convo_block = "\n\n".join(
#         f"Conversation ID: {c['conversation_id']}\nTranscript:\n{c['conversation_text']}"
#         for c in batch
#     )

#     prompt = f"""You are a Senior QA Analyst for an EMI Recovery Voicebot (Hinglish calls).

# {_format_context(context_path)}

# Read the conversations below and identify the DISTINCT, RECOGNIZABLE patterns
# of customer behaviour or situation actually present in THIS batch. Do not use
# any predefined template or fixed list - name what you actually see, in the
# specific, natural language a QA analyst would use.

# Rules:
# - Propose between {min_labels} and {max_labels} labels. If everything in this
#   batch is really the same situation, propose fewer (even 1) - do not force
#   artificial variety just to fill a quota.
# - Each label must be specific enough to be useful (not vague like "Other
#   discussion") but general enough that more than one conversation could
#   plausibly belong to it.
# - A label must NOT just restate something already listed in the context
#   above - it should describe something MORE specific than its parent.

# Return ONLY valid JSON, no markdown, no extra text:
# [
#   {{"name": "short label (2-5 words)", "description": "one sentence describing this pattern"}}
# ]

# Conversations:

# {convo_block}
# """
#     response = _call_llm_guarded(prompt, max_tokens=600)
#     raw = (response.choices[0].message.content or "").strip()
#     return _safe_parse_list(raw, "_propose_labels")


# # ------------------------------------------------------------------
# # STAGE 1b - canonicalize. Different batches will describe the same
# # real pattern with different wording ("Payment Tomorrow" vs "Will pay
# # tomorrow") - this is what merges those into one final set, without
# # falling back to a hand-written enum.
# # ------------------------------------------------------------------
# def _canonicalize_labels(candidates: list[dict], context_path: list[tuple[str, str]],
#                           max_final: int = 8) -> list[dict]:
#     if not candidates:
#         return [{"name": "Other", "description": "Does not fit a clearer pattern."}]

#     candidate_block = "\n".join(
#         f'- "{c.get("name", "")}": {c.get("description", "")}'
#         for c in candidates if c.get("name")
#     )

#     prompt = f"""You are consolidating candidate groupings proposed independently across
# several small batches of the SAME set of conversations.

# {_format_context(context_path)}

# Candidates proposed so far (some are near-duplicates or overlapping, worded
# differently by different passes):
# {candidate_block}

# Merge these into a final, de-duplicated list of at most {max_final} distinct
# labels that best represent the real, DISTINCT patterns across all candidates.
# - Combine near-duplicates (different wording, same meaning) into one label,
#   picking the clearest name.
# - Drop labels that are too narrow or one-off to be useful; fold them into
#   "Other" instead.
# - Always include exactly one catch-all label named "Other".

# Return ONLY valid JSON, no markdown:
# [
#   {{"name": "final label name", "description": "one sentence"}}
# ]
# """
#     response = _call_llm_guarded(prompt, max_tokens=500)
#     raw = (response.choices[0].message.content or "").strip()
#     final = _safe_parse_list(raw, "_canonicalize_labels")

#     if not final:
#         return [{"name": "Other", "description": "Does not fit a clearer pattern."}]

#     if not any(l.get("name", "").strip().lower() == "other" for l in final):
#         final.append({"name": "Other", "description": "Does not fit a clearer pattern."})

#     return final


# def _normalize_to_label(raw_name, labels: list[dict], fallback: str = "Other") -> str:
#     if not raw_name:
#         return fallback
#     cleaned = raw_name.strip().lower()
#     for l in labels:
#         if cleaned == l["name"].strip().lower():
#             return l["name"]
#     return fallback


# # ------------------------------------------------------------------
# # STAGE 2 - classify every conversation against the FINAL canonical
# # label set for this node (closed at this point, but discovered from
# # the actual data instead of hardcoded).
# # ------------------------------------------------------------------
# def _classify_batch(batch: list[dict], labels: list[dict],
#                      context_path: list[tuple[str, str]]) -> list[dict]:
#     label_block = "\n".join(f'- "{l["name"]}": {l.get("description", "")}' for l in labels)
#     convo_block = "\n\n".join(
#         f"Conversation ID: {c['conversation_id']}\nTranscript:\n{c['conversation_text']}"
#         for c in batch
#     )

#     prompt = f"""{_format_context(context_path)}

# Assign EACH conversation below to EXACTLY ONE of these labels (copy the name
# exactly as written). If nothing else genuinely fits, use "Other" - it's a
# valid, real answer.

# {label_block}

# Return ONLY valid JSON, no markdown:
# [
#   {{"conversation_id": 123, "label": "{labels[0]['name']}"}}
# ]

# Conversations:

# {convo_block}
# """
#     response = _call_llm_guarded(prompt, max_tokens=500)
#     raw = (response.choices[0].message.content or "").strip()
#     items = _safe_parse_list(raw, "_classify_batch")
#     for item in items:
#         item["label"] = _normalize_to_label(item.get("label"), labels)
#     return items


# def discover_and_classify(conversations: list[dict], context_path: list[tuple[str, str]],
#                            discovery_batch_size: int = 8, classify_batch_size: int = 5,
#                            max_workers: int = 4, notify=lambda msg: None
#                            ) -> tuple[list[dict], dict]:
#     """
#     One full level of the tree: propose -> canonicalize -> classify.
#     Both LLM stages run their batches IN PARALLEL (ThreadPoolExecutor) instead
#     of one-by-one - this is what actually makes a 50-conversation run take
#     seconds instead of feeling stuck for minutes with zero feedback.
#     Returns (labels, groups) where groups maps label name -> conversations.
#     """
#     discovery_batches = _chunks(conversations, discovery_batch_size)
#     candidates = []

#     notify(f"proposing labels across {len(discovery_batches)} batch(es)...")
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         futures = {executor.submit(_propose_labels, b, context_path): b for b in discovery_batches}
#         done = 0
#         for future in as_completed(futures):
#             candidates.extend(future.result())
#             done += 1
#             notify(f"  proposal batch {done}/{len(discovery_batches)} done")

#     if len(discovery_batches) <= 1:
#         # nothing to merge across batches when there was only one batch -
#         # this produces the SAME final label set as canonicalizing would,
#         # just without the redundant extra LLM call
#         seen = set()
#         labels = []
#         for c in candidates:
#             name = c.get("name", "").strip()
#             if name and name.lower() not in seen:
#                 seen.add(name.lower())
#                 labels.append({"name": name, "description": c.get("description", "")})
#         if not labels:
#             labels = [{"name": "Other", "description": "Does not fit a clearer pattern."}]
#         if not any(l["name"].strip().lower() == "other" for l in labels):
#             labels.append({"name": "Other", "description": "Does not fit a clearer pattern."})
#     else:
#         notify("canonicalizing labels...")
#         labels = _canonicalize_labels(candidates, context_path)
#     notify(f"final labels: {', '.join(l['name'] for l in labels)}")

#     convo_lookup = {c["conversation_id"]: c for c in conversations}
#     classify_batches = _chunks(conversations, classify_batch_size)
#     groups = defaultdict(list)

#     notify(f"classifying {len(conversations)} conversation(s) across {len(classify_batches)} batch(es)...")
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         futures = {executor.submit(_classify_batch, b, labels, context_path): b for b in classify_batches}
#         done = 0
#         for future in as_completed(futures):
#             for item in future.result():
#                 convo = convo_lookup.get(item.get("conversation_id"))
#                 if convo is None:
#                     continue
#                 groups[item["label"]].append(convo)
#             done += 1
#             notify(f"  classify batch {done}/{len(classify_batches)} done")

#     return labels, groups


# # next-level naming is cosmetic only (shows up as a "level" field on each
# # node) - it does NOT constrain what the LLM is allowed to discover there.
# _LEVEL_SEQUENCE = ["subgroup", "bucket", "breakdown"]


# def _next_level_name(level_name: str) -> str:
#     if level_name in _LEVEL_SEQUENCE:
#         idx = _LEVEL_SEQUENCE.index(level_name)
#         if idx + 1 < len(_LEVEL_SEQUENCE):
#             return _LEVEL_SEQUENCE[idx + 1]
#     return "detail"


# def build_dynamic_tree(
#     conversations: list[dict],
#     context_path: list[tuple[str, str]],
#     level_name: str = "subgroup",
#     depth: int = 0,
#     max_depth: int = 3,
#     min_conversations_to_split: int = 6,
#     sample_count: int = 5,
#     max_workers: int = 4,
#     notify=lambda msg: None,
# ) -> dict:
#     """
#     Recursively discovers as many levels of granularity as the data
#     actually supports. For "Positive" you might get
#     Promise to Pay -> Payment Tomorrow -> Thru UPI. For "Neutral" the
#     whole tree can look completely different - nothing below the
#     top-level category is hardcoded.

#     Stops recursing into a branch when:
#       - max_depth is reached, or
#       - too few conversations remain to meaningfully split, or
#       - discovery collapses to a single real label (nothing further to say)
#     """
#     samples = [
#         {"conversation_id": c["conversation_id"], "preview": c["conversation_text"]}
#         for c in conversations[:sample_count]
#     ]

#     node = {
#         "name": None,          # filled in by the caller (the label chosen at the parent level)
#         "level": level_name,
#         "count": len(conversations),
#         "description": "",
#         "children": [],
#         "sample_conversations": samples,
#     }

#     path_label = " > ".join(name for _, name in context_path) or "top level"

#     if depth >= max_depth or len(conversations) < min_conversations_to_split:
#         notify(f"stopping at {path_label} ({len(conversations)} convo(s), depth {depth}) - nothing further to split")
#         return node

#     notify(f"analyzing {level_name}s under {path_label} ({len(conversations)} convo(s))...")
#     labels, groups = discover_and_classify(
#         conversations, context_path, max_workers=max_workers, notify=notify
#     )
#     # real_labels = [l for l in labels if groups.get(l["name"])]
#     real_labels = [l for l in labels if l.get("name") and groups.get(l["name"])]

#     if len(real_labels) <= 1:
#         notify(f"{path_label} collapsed to a single pattern - stopping here")
#         return node

#     # Each label's subtree is completely independent of its siblings - build
#     # them concurrently instead of one at a time. This is what actually cuts
#     # wall-clock time: it does NOT skip a single discovery/classify call, it
#     # just stops making sibling branches wait in line behind each other.
#     # The global _llm_semaphore above keeps total concurrent LLM requests
#     # capped regardless of how many branches are running at once.
#     children = []
#     with ThreadPoolExecutor(max_workers=min(len(real_labels), max_workers)) as executor:
#         future_to_label = {
#             executor.submit(
#                 build_dynamic_tree,
#                 groups[label["name"]],
#                 context_path + [(level_name, label["name"])],
#                 _next_level_name(level_name),
#                 depth + 1,
#                 max_depth,
#                 min_conversations_to_split,
#                 sample_count,
#                 max_workers,
#                 notify,
#             ): label
#             for label in real_labels
#         }
#         for future in as_completed(future_to_label):
#             label = future_to_label[future]
#             subtree = future.result()
#             subtree["name"] = label["name"]
#             subtree["description"] = label.get("description", "")
#             children.append(subtree)

#     children.sort(key=lambda x: x["count"], reverse=True)
#     node["children"] = children
#     return node


# def run_direct_pipeline(
#     source,
#     campaign_id: int,
#     from_date,
#     to_date,
#     category: str = None,
#     limit: int | None = None,
#     batch_size: int = 5,
#     max_workers: int = 4,
#     on_progress=None,
#     max_depth: int = 3,
#     min_conversations_to_split: int = 6,
# ):
#     def notify(msg):
#         if on_progress:
#             on_progress(msg)
#         print(f"[direct_pipeline] {msg}")

#     notify("Fetching conversations...")
#     convos = source.get_conversations(campaign_id, from_date, to_date, category=category, limit=limit)
#     usable = [c for c in convos if c["conversation_text"]]
#     notify(f"{len(usable)} usable conversations")

#     context_path = [("category", category)] if category else []

#     notify("Discovering subgroups...")
#     tree = build_dynamic_tree(
#         usable,
#         context_path,
#         level_name="subgroup",
#         max_depth=max_depth,
#         min_conversations_to_split=min_conversations_to_split,
#         max_workers=max_workers,
#         notify=notify,
#     )

#     clusters = tree["children"]
#     if not clusters:
#         # not enough conversations, or the batch was too homogeneous to split -
#         # surface it as a single cluster instead of an empty result
#         tree["name"] = category or "All"
#         clusters = [tree]

#     for c in clusters:
#         print(f"\n=== {c['name']} ({c['count']}) ===")
#         print(json.dumps(c["children"], indent=2, ensure_ascii=False))

#     notify("Finished.")

#     return {
#         "total_conversations": len(convos),
#         "usable_conversations": len(usable),
#         "categories": {
#             category: {
#                 "total": len(usable),
#                 "clusters": clusters,
#             }
#         },
#     }















import json
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.aiml.naming import _call_llm

# Hard cap on concurrent LLM requests across the WHOLE pipeline, no matter how
# many threads end up queued (batch-level parallelism + sibling-branch
# parallelism together). Tune this to whatever your gateway can actually
# handle concurrently - raising it doesn't change any analysis output, only
# how many requests can be in flight at once.
_MAX_CONCURRENT_LLM_CALLS = 1
_llm_semaphore = threading.Semaphore(_MAX_CONCURRENT_LLM_CALLS)


def _call_llm_guarded(prompt: str, max_tokens: int):
    return _call_llm(prompt, max_tokens=max_tokens, semaphore=_llm_semaphore)


def _extract_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _safe_parse_list(raw: str, caller: str) -> list[dict]:
    try:
        parsed = json.loads(_extract_json(raw))
    except Exception:
        print(f"    [{caller}] failed to parse, raw={raw!r}")
        return []

    if isinstance(parsed, dict):
        parsed = [parsed]

    if not isinstance(parsed, list):
        print(f"    [{caller}] parsed JSON was not a list or object, raw={raw!r}")
        return []

    return [item for item in parsed if isinstance(item, dict)]


def _chunks(lst: list, n: int) -> list[list]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


CATEGORY_MEANINGS = {
    "positive": "the bot got what it wanted - a CLEAR, CERTAIN commitment such as a specific payment date or timeframe.",
    "negative": "the customer did not engage meaningfully - no reply, stayed silent, or the call had no real conversation.",
    "neutral": "the customer responded but was UNCLEAR or NON-COMMITTAL - no date or timeframe given with certainty.",
}


def _format_context(context_path: list[tuple[str, str]]) -> str:
    """
    context_path is the chain of decisions already made above this node,
    e.g. [("category", "Positive"), ("subgroup", "Promise to Pay")].
    This is what stops the LLM from re-discovering the parent as a child,
    and lets it condition on what's already known.
    """
    if not context_path:
        return "This is the top level - no parent grouping has been decided yet."

    lines = []
    for level, name in context_path:
        if level == "category":
            meaning = CATEGORY_MEANINGS.get(name.strip().lower())
            lines.append(f'- top-level category: "{name}"' + (f" ({meaning})" if meaning else ""))
        else:
            lines.append(f'- {level}: "{name}"')

    return "These conversations already belong to:\n" + "\n".join(lines)


# ------------------------------------------------------------------
# STAGE 1a - free discovery. No fixed template: the LLM looks at one
# small batch and names whatever patterns are actually there.
# ------------------------------------------------------------------
def _propose_labels(batch: list[dict], context_path: list[tuple[str, str]],
                     min_labels: int = 1, max_labels: int = 6) -> list[dict]:
    convo_block = "\n\n".join(
        f"Conversation ID: {c['conversation_id']}\nTranscript:\n{c['conversation_text']}"
        for c in batch
    )

    prompt = f"""You are a Senior QA Analyst for an EMI Recovery Voicebot (Hinglish calls).

{_format_context(context_path)}

Read the conversations below and identify the DISTINCT, RECOGNIZABLE patterns
of customer behaviour or situation actually present in THIS batch. Do not use
any predefined template or fixed list - name what you actually see, in the
specific, natural language a QA analyst would use.

Rules:
- Propose between {min_labels} and {max_labels} labels. If everything in this
  batch is really the same situation, propose fewer (even 1) - do not force
  artificial variety just to fill a quota.
- Each label must be specific enough to be useful (not vague like "Other
  discussion") but general enough that more than one conversation could
  plausibly belong to it.
- A label must NOT just restate something already listed in the context
  above - it should describe something MORE specific than its parent.

Return ONLY valid JSON, no markdown, no extra text:
[
  {{"name": "short label (2-5 words)", "description": "one sentence describing this pattern"}}
]

Conversations:

{convo_block}
"""
    response = _call_llm_guarded(prompt, max_tokens=600)
    raw = (response.choices[0].message.content or "").strip()
    return _safe_parse_list(raw, "_propose_labels")


# ------------------------------------------------------------------
# STAGE 1b - canonicalize. Different batches will describe the same
# real pattern with different wording ("Payment Tomorrow" vs "Will pay
# tomorrow") - this is what merges those into one final set, without
# falling back to a hand-written enum.
# ------------------------------------------------------------------
def _canonicalize_labels(candidates: list[dict], context_path: list[tuple[str, str]],
                          max_final: int = 8) -> list[dict]:
    if not candidates:
        return [{"name": "Other", "description": "Does not fit a clearer pattern."}]

    candidate_block = "\n".join(
        f'- "{c.get("name", "")}": {c.get("description", "")}'
        for c in candidates if c.get("name")
    )

    prompt = f"""You are consolidating candidate groupings proposed independently across
several small batches of the SAME set of conversations.

{_format_context(context_path)}

Candidates proposed so far (some are near-duplicates or overlapping, worded
differently by different passes):
{candidate_block}

Merge these into a final, de-duplicated list of at most {max_final} distinct
labels that best represent the real, DISTINCT patterns across all candidates.
- Combine near-duplicates (different wording, same meaning) into one label,
  picking the clearest name.
- Drop labels that are too narrow or one-off to be useful; fold them into
  "Other" instead.
- Always include exactly one catch-all label named "Other".

Return ONLY valid JSON, no markdown:
[
  {{"name": "final label name", "description": "one sentence"}}
]
"""
    response = _call_llm_guarded(prompt, max_tokens=500)
    raw = (response.choices[0].message.content or "").strip()
    final = _safe_parse_list(raw, "_canonicalize_labels")

    # Drop any item missing a usable "name" right here, at the source.
    # This is the ONE place that matters - _classify_batch, _normalize_to_label,
    # and build_dynamic_tree all do direct l["name"] access downstream with no
    # further safety net, so a malformed LLM response (missing "name") would
    # otherwise crash the whole run with KeyError('name') wherever it's first
    # touched. Filtering here means nothing malformed ever reaches those spots.
    final = [l for l in final if l.get("name") and l["name"].strip()]

    if not final:
        return [{"name": "Other", "description": "Does not fit a clearer pattern."}]

    if not any(l.get("name", "").strip().lower() == "other" for l in final):
        final.append({"name": "Other", "description": "Does not fit a clearer pattern."})

    return final


def _normalize_to_label(raw_name, labels: list[dict], fallback: str = "Other") -> str:
    if not raw_name:
        return fallback
    cleaned = raw_name.strip().lower()
    for l in labels:
        if cleaned == l["name"].strip().lower():
            return l["name"]
    return fallback


# ------------------------------------------------------------------
# STAGE 2 - classify every conversation against the FINAL canonical
# label set for this node (closed at this point, but discovered from
# the actual data instead of hardcoded).
# ------------------------------------------------------------------
def _classify_batch(batch: list[dict], labels: list[dict],
                     context_path: list[tuple[str, str]]) -> list[dict]:
    label_block = "\n".join(f'- "{l["name"]}": {l.get("description", "")}' for l in labels)
    convo_block = "\n\n".join(
        f"Conversation ID: {c['conversation_id']}\nTranscript:\n{c['conversation_text']}"
        for c in batch
    )

    prompt = f"""{_format_context(context_path)}

Assign EACH conversation below to EXACTLY ONE of these labels (copy the name
exactly as written). If nothing else genuinely fits, use "Other" - it's a
valid, real answer.

{label_block}

Return ONLY valid JSON, no markdown:
[
  {{"conversation_id": 123, "label": "{labels[0]['name']}"}}
]

Conversations:

{convo_block}
"""
    response = _call_llm_guarded(prompt, max_tokens=500)
    raw = (response.choices[0].message.content or "").strip()
    items = _safe_parse_list(raw, "_classify_batch")
    for item in items:
        item["label"] = _normalize_to_label(item.get("label"), labels)
    return items


def discover_and_classify(conversations: list[dict], context_path: list[tuple[str, str]],
                           discovery_batch_size: int = 8, classify_batch_size: int = 5,
                           max_workers: int = 4, notify=lambda msg: None
                           ) -> tuple[list[dict], dict]:
    """
    One full level of the tree: propose -> canonicalize -> classify.
    Both LLM stages run their batches IN PARALLEL (ThreadPoolExecutor) instead
    of one-by-one - this is what actually makes a 50-conversation run take
    seconds instead of feeling stuck for minutes with zero feedback.
    Returns (labels, groups) where groups maps label name -> conversations.
    """
    discovery_batches = _chunks(conversations, discovery_batch_size)
    candidates = []

    notify(f"proposing labels across {len(discovery_batches)} batch(es)...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_propose_labels, b, context_path): b for b in discovery_batches}
        done = 0
        for future in as_completed(futures):
            candidates.extend(future.result())
            done += 1
            notify(f"  proposal batch {done}/{len(discovery_batches)} done")

    if len(discovery_batches) <= 1:
        # nothing to merge across batches when there was only one batch -
        # this produces the SAME final label set as canonicalizing would,
        # just without the redundant extra LLM call
        seen = set()
        labels = []
        for c in candidates:
            name = c.get("name", "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                labels.append({"name": name, "description": c.get("description", "")})
        if not labels:
            labels = [{"name": "Other", "description": "Does not fit a clearer pattern."}]
        if not any(l["name"].strip().lower() == "other" for l in labels):
            labels.append({"name": "Other", "description": "Does not fit a clearer pattern."})
    else:
        notify("canonicalizing labels...")
        labels = _canonicalize_labels(candidates, context_path)
    notify(f"final labels: {', '.join(l['name'] for l in labels)}")

    convo_lookup = {c["conversation_id"]: c for c in conversations}
    classify_batches = _chunks(conversations, classify_batch_size)
    groups = defaultdict(list)

    notify(f"classifying {len(conversations)} conversation(s) across {len(classify_batches)} batch(es)...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_classify_batch, b, labels, context_path): b for b in classify_batches}
        done = 0
        for future in as_completed(futures):
            for item in future.result():
                convo = convo_lookup.get(item.get("conversation_id"))
                if convo is None:
                    continue
                groups[item["label"]].append(convo)
            done += 1
            notify(f"  classify batch {done}/{len(classify_batches)} done")

    return labels, groups


# next-level naming is cosmetic only (shows up as a "level" field on each
# node) - it does NOT constrain what the LLM is allowed to discover there.
_LEVEL_SEQUENCE = ["subgroup", "bucket", "breakdown"]


def _next_level_name(level_name: str) -> str:
    if level_name in _LEVEL_SEQUENCE:
        idx = _LEVEL_SEQUENCE.index(level_name)
        if idx + 1 < len(_LEVEL_SEQUENCE):
            return _LEVEL_SEQUENCE[idx + 1]
    return "detail"


def build_dynamic_tree(
    conversations: list[dict],
    context_path: list[tuple[str, str]],
    level_name: str = "subgroup",
    depth: int = 0,
    max_depth: int = 3,
    min_conversations_to_split: int = 6,
    sample_count: int = 5,
    max_workers: int = 4,
    notify=lambda msg: None,
) -> dict:
    """
    Recursively discovers as many levels of granularity as the data
    actually supports. For "Positive" you might get
    Promise to Pay -> Payment Tomorrow -> Thru UPI. For "Neutral" the
    whole tree can look completely different - nothing below the
    top-level category is hardcoded.

    Stops recursing into a branch when:
      - max_depth is reached, or
      - too few conversations remain to meaningfully split, or
      - discovery collapses to a single real label (nothing further to say)
    """
    samples = [
        {"conversation_id": c["conversation_id"], "preview": c["conversation_text"]}
        for c in conversations[:sample_count]
    ]

    node = {
        "name": None,          # filled in by the caller (the label chosen at the parent level)
        "level": level_name,
        "count": len(conversations),
        "description": "",
        "children": [],
        "sample_conversations": samples,
    }

    path_label = " > ".join(name for _, name in context_path) or "top level"

    if depth >= max_depth or len(conversations) < min_conversations_to_split:
        notify(f"stopping at {path_label} ({len(conversations)} convo(s), depth {depth}) - nothing further to split")
        return node

    notify(f"analyzing {level_name}s under {path_label} ({len(conversations)} convo(s))...")
    labels, groups = discover_and_classify(
        conversations, context_path, max_workers=max_workers, notify=notify
    )
    # kept as a second safety net even though _canonicalize_labels now filters
    # at the source - harmless belt-and-braces, costs nothing
    real_labels = [l for l in labels if l.get("name") and groups.get(l["name"])]

    if len(real_labels) <= 1:
        notify(f"{path_label} collapsed to a single pattern - stopping here")
        return node

    # Each label's subtree is completely independent of its siblings - build
    # them concurrently instead of one at a time. This is what actually cuts
    # wall-clock time: it does NOT skip a single discovery/classify call, it
    # just stops making sibling branches wait in line behind each other.
    # The global _llm_semaphore above keeps total concurrent LLM requests
    # capped regardless of how many branches are running at once.
    children = []
    with ThreadPoolExecutor(max_workers=min(len(real_labels), max_workers)) as executor:
        future_to_label = {
            executor.submit(
                build_dynamic_tree,
                groups[label["name"]],
                context_path + [(level_name, label["name"])],
                _next_level_name(level_name),
                depth + 1,
                max_depth,
                min_conversations_to_split,
                sample_count,
                max_workers,
                notify,
            ): label
            for label in real_labels
        }
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            subtree = future.result()
            subtree["name"] = label["name"]
            subtree["description"] = label.get("description", "")
            children.append(subtree)

    children.sort(key=lambda x: x["count"], reverse=True)
    node["children"] = children
    return node


def run_direct_pipeline(
    source,
    campaign_id: int,
    from_date,
    to_date,
    category: str = None,
    limit: int | None = None,
    batch_size: int = 5,
    max_workers: int = 4,
    on_progress=None,
    max_depth: int = 3,
    min_conversations_to_split: int = 6,
):
    def notify(msg):
        if on_progress:
            on_progress(msg)
        print(f"[direct_pipeline] {msg}")

    notify("Fetching conversations...")
    convos = source.get_conversations(campaign_id, from_date, to_date, category=category, limit=limit)
    usable = [c for c in convos if c["conversation_text"]]
    notify(f"{len(usable)} usable conversations")

    context_path = [("category", category)] if category else []

    notify("Discovering subgroups...")
    tree = build_dynamic_tree(
        usable,
        context_path,
        level_name="subgroup",
        max_depth=max_depth,
        min_conversations_to_split=min_conversations_to_split,
        max_workers=max_workers,
        notify=notify,
    )

    clusters = tree["children"]
    if not clusters:
        # not enough conversations, or the batch was too homogeneous to split -
        # surface it as a single cluster instead of an empty result
        tree["name"] = category or "All"
        clusters = [tree]

    for c in clusters:
        print(f"\n=== {c['name']} ({c['count']}) ===")
        print(json.dumps(c["children"], indent=2, ensure_ascii=False))

    notify("Finished.")

    return {
        "total_conversations": len(convos),
        "usable_conversations": len(usable),
        "categories": {
            category: {
                "total": len(usable),
                "clusters": clusters,
            }
        },
    }