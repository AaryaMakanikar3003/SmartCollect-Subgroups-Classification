import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.aiml.naming import _call_llm  


# def classify_batch(convo_batch: list[dict]) -> list[dict]:
#     """
#     Sends one batch of conversations to the LLM. The LLM decides category
#     AND subgroup for each one, using the existing 'Conclusion' tag only as
#     a hint it can agree or disagree with.
#     """
#     convo_block = "\n\n".join(
#         f"--- Conversation id={c['conversation_id']} (system hint: \"{c['top_level_category'] or 'none'}\") ---\n"
#         f"{c['conversation_text'][:1200]}"
#         for c in convo_batch
#     )

#     prompt = f"""You are analyzing debt-collection voicebot call transcripts (Hinglish, EMI recovery).

# For each conversation below, decide its outcome CATEGORY (e.g. Positive, Negative, Neutral, Already Paid,
# Callback, Doubtful, Denied, Wrong Number, or your own better category if none fit) and a specific SUBGROUP
# within that category describing the distinct pattern (e.g. "Timeline commitment - Diwali", "Timeline
# commitment - 1 week", "Vague agreement, no date given", "Silent, no response").

# Each conversation also shows a "system hint" — the category our existing system guessed. Use it as a
# reference, but decide based on the actual conversation content; override it if the content disagrees.

# Respond with ONLY a JSON array, one object per conversation, in this exact shape:
# [{{"conversation_id": 123, "category": "...", "subgroup": "...", "subgroup_definition": "one line"}}]

# {convo_block}"""

#     response = _call_llm(prompt, max_tokens=2000)
#     raw = (response.choices[0].message.content or "").strip()
#     try:
#         parsed = json.loads(raw)
#         return parsed if isinstance(parsed, list) else []
#     except json.JSONDecodeError:
#         print(f"    [direct_pipeline] batch failed to parse, raw={raw[:150]!r}")
#         return []

# def reconcile_subgroups(all_classifications: list[dict]) -> dict:
#     """
#     Different batches may invent slightly different names for the same
#     real pattern. This asks the LLM once to merge near-duplicates into a
#     canonical taxonomy: {raw_name: canonical_name}
#     """
#     unique_pairs = {}
#     for c in all_classifications:
#         key = (c.get("category"), c.get("subgroup"))
#         if key not in unique_pairs and c.get("subgroup"):
#             unique_pairs[key] = c.get("subgroup_definition", "")

#     if not unique_pairs:
#         return {}

#     listing = "\n".join(
#         f'- category="{cat}", subgroup="{sub}", definition="{definition}"'
#         for (cat, sub), definition in unique_pairs.items()
#     )

#     prompt = f"""Here is a list of (category, subgroup) pairs discovered across different batches of the
# same dataset. Some subgroups are near-duplicates describing the same real pattern with different wording
# (e.g. "Payment Deferral" and "Delayed Payment Promise" might be the same thing).

# Merge near-duplicates within the SAME category into one canonical subgroup name. Keep genuinely distinct
# subgroups separate. Respond with ONLY a JSON object mapping each original subgroup name to its canonical
# name (use the same name if it doesn't need merging):
# {{"original_subgroup_name": "canonical_subgroup_name", ...}}

# {listing}"""

#     response = _call_llm(prompt, max_tokens=1500)
#     raw = (response.choices[0].message.content or "").strip()
#     try:
#         return json.loads(raw)
#     except json.JSONDecodeError:
        # return {}  
        
def discover_subgroups(convo_batch: list[dict]) -> list[dict]:
    print(">>> discover_subgroups started")

    convo_block = "\n\n".join(
        f"""
Conversation ID: {c['conversation_id']}

Transcript:
{c['conversation_text'][:1500]}
"""
        for c in convo_batch
    )

    prompt = f"""
You are a Senior QA Analyst for an EMI Recovery Voicebot.

IMPORTANT

All conversations below already belong to the SAME top-level category.

DO NOT classify the category again.

Your only job is to discover the behavioural subgroup each conversation belongs to.

Create business-friendly subgroup names.

Examples:

Festival Based Payment Promise

Salary Based Payment Promise

Already Paid

Customer Requested Callback

Settlement Request

Silent Customer

Disconnected Call

Payment Next Week

Payment Next Month

Family Member Answered

Wrong Number

etc.

Rules

- Similar conversations MUST receive exactly the same subgroup name.

- Never invent a new wording if one already exists.

- Keep subgroup names short.

Return ONLY valid JSON.

[
{{
"conversation_id":123,
"subgroup":"Festival Based Payment Promise"
}}
]

Conversations

{convo_block}
"""
    print(">>> Calling LLM...")
    response = _call_llm(prompt,max_tokens=512)
    print(">>> LLM returned")

    raw=(response.choices[0].message.content or "").strip()

    try:
        return json.loads(raw)
    except:
        print(raw)
        return []      
    

def analyze_subgroup(subgroup_name: str, conversations: list[dict]) -> dict:

    convo_text = "\n\n".join(
        f"""
Conversation ID: {c['conversation_id']}

Transcript:
{c['conversation_text'][:1500]}
"""
        for c in conversations
    )

    prompt = f"""
You are a Senior Debt Collection QA Analyst.

You are given multiple conversations that all belong to the subgroup:

{subgroup_name}

Analyze them deeply.

Return ONLY valid JSON.

{{
"summary":"...",

"customer_behavior":"...",

"payment_intent":"High/Medium/Low",

"common_patterns":[
"...",
"..."
],

"breakdown":[
{{
"name":"...",
"description":"...",
"count":0
}}
],

"insights":[
"...",
"..."
]
}}

Conversations

{convo_text}
"""

    response = _call_llm(prompt, max_tokens=512)

    raw = (response.choices[0].message.content or "").strip()

    try:
        return json.loads(raw)
    except Exception:
        print(raw)
        return {}      


def run_direct_pipeline(
    source,
    campaign_id: int,
    from_date,
    to_date,
    category: str = None,
    limit: int | None = None,
    batch_size: int = 10,
    max_workers: int = 1,
    on_progress=None,
):
    def notify(msg):
        if on_progress:
            on_progress(msg)
        print(f"[direct_pipeline] {msg}")

    notify("Fetching conversations...")

    convos = source.get_conversations(
        campaign_id,
        from_date,
        to_date,
        category=category,
        limit=limit,
    )

    usable = [c for c in convos if c["conversation_text"]]

    notify(f"{len(usable)} usable conversations, splitting into batches of {batch_size}...")

    batches = [
        usable[i:i + batch_size]
        for i in range(0, len(usable), batch_size)
    ]

    all_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {
            executor.submit(discover_subgroups, batch): batch
            for batch in batches
        }

        finished = 0

        for future in as_completed(futures):
            try:
                print("Waiting for batch...")
                result = future.result()
                print("Batch finished")
                all_results.extend(result)
            except Exception as e:
                notify(f"Batch failed: {e}")

            finished += 1
            notify(f"Processed batch {finished}/{len(batches)}")

    grouped = defaultdict(list)

    convo_lookup = {
        c["conversation_id"]: c
        for c in usable
    }

    for item in all_results:

        convo = convo_lookup.get(item["conversation_id"])

        if convo is None:
            continue

        subgroup = item.get("subgroup", "Other")

        grouped[subgroup].append(convo)

    notify("Building final response...")

    response = {
        "total_conversations": len(convos),
        "usable_conversations": len(usable),
        "categories": {}
    }

    # category_dict = defaultdict(list)

    # for (category_name, subgroup_name), rows in grouped.items():

    #     description = rows[0].get(
    #         "subgroup_definition",
    #         ""
    #     )

    #     samples = []

    #     for r in rows[:5]:

    #         convo = convo_lookup.get(r["conversation_id"])

    #         if convo:

    #             samples.append(
    #                 {
    #                     "conversation_id": convo["conversation_id"],
    #                     "preview": convo["conversation_text"][:1500]
    #                 }
    #             )

    #     cluster = {
    #         "name": subgroup_name,
    #         "description": description,
    #         "count": len(rows),
    #         "sample_conversations": samples
    #     }

    #     category_dict[category_name].append(cluster)
    clusters = []

    for subgroup_name, subgroup_conversations in grouped.items():

        notify(f"Analyzing subgroup: {subgroup_name}")

        analysis = analyze_subgroup(
            subgroup_name,
            subgroup_conversations
        )

        samples = []

        for convo in subgroup_conversations[:5]:

            samples.append({
                "conversation_id": convo["conversation_id"],
                "preview": convo["conversation_text"][:1500]
            })

        clusters.append({

            "name": subgroup_name,

            "description": analysis.get("summary", ""),

            "count": len(subgroup_conversations),

            "customer_behavior": analysis.get("customer_behavior", ""),

            "payment_intent": analysis.get("payment_intent", ""),

            "common_patterns": analysis.get("common_patterns", []),

            "breakdown": analysis.get("breakdown", []),

            "insights": analysis.get("insights", []),

            "sample_conversations": samples

        })

    # for category_name, clusters in category_dict.items():

    #     clusters.sort(
    #         key=lambda x: x["count"],
    #         reverse=True
    #     )

    #     response["categories"][category_name] = {
    #         "total": sum(c["count"] for c in clusters),
    #         "clusters": clusters
    #     }

    # notify("Finished.")

    # return response
    clusters.sort(key=lambda x: x["count"], reverse=True)

    response["categories"][category] = {
        "total": len(usable),
        "clusters": clusters
    }

    notify("Finished.")
    
    print(json.dumps(response, indent=2))
    return response