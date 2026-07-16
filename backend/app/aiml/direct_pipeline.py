import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.aiml.naming import _call_llm  


def _extract_json(raw: str) -> str:
    """
    Strips markdown code fences (```json ... ``` or ``` ... ```) that LLMs
    sometimes wrap around JSON output, so json.loads() doesn't choke on them.
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

        
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
DO NOT classify the top-level category again.
Your ONLY job is to identify the SINGLE MOST APPROPRIATE behavioural subgroup for each conversation.
Always identify the PRIMARY behaviour of the customer, NOT simply the final outcome of the call.
-------------------------
PRIORITY ORDER
-------------------------
If multiple behaviours exist, ALWAYS choose the highest priority behaviour.
Priority (highest → lowest):
1. Fraud / Scam Suspicion
2. Payment Record Dispute
3. Outstanding Amount Dispute
4. Already Paid Claim
5. Loan Ownership / Account Dispute
6. Wrong Number
7. Family Member Answered
8. Settlement Request
9. Callback Request
10. Silent / Disconnected
11. Payment Promise

Payment Promise should ONLY be selected when there is NO stronger dispute behaviour.
-------------------------
IMPORTANT RULES
-------------------------
If customer says things like:
"I already paid."
"I gave money to your executive."
"I paid Ankit."
"I already deposited money."
"I have already paid an installment."
"Our records are wrong."
"Outstanding amount is incorrect."
"I don't trust this amount."
"You are asking again although I already paid."

THEN classify as one of:
• Payment Record Dispute
• Outstanding Amount Dispute
• Already Paid Claim

NOT Payment Promise.
Even if later in the conversation the customer says:
"I'll pay next week."
"I'll pay on 12th."
"I'll pay one installment."
DO NOT classify as Payment Promise if the root issue is still a dispute.
-------------------------
EXAMPLES
-------------------------
Example 1
Customer:
"I already paid ₹2400 to Ankit."
Bot:
"Our records still show dues."
Customer:
"I'll pay on 12th."

Subgroup:
Payment Record Dispute

NOT:
Payment Promise


Example 2
Customer:
"I already cleared my payment."
Bot:
"Our records show pending."

Subgroup:
Already Paid Claim

Example 3
Customer:
"The outstanding amount is wrong."

Subgroup:
Outstanding Amount Dispute


Example 4
Customer:
"This looks like fraud."

Subgroup:
Fraud / Scam Suspicion


Example 5
Customer:
"I'll pay after salary on 5th."
Bot:
"Okay."

Subgroup:
Salary Based Payment Promise


Example 6
Customer:
"I'll pay after Diwali."

Subgroup:
Festival Based Payment Promise


-------------------------
NAMING RULES
-------------------------
Use short, business-friendly subgroup names.
Reuse existing wording whenever possible.
Examples of valid subgroup names:
Fraud / Scam Suspicion
Payment Record Dispute
Outstanding Amount Dispute
Already Paid Claim
Salary Based Payment Promise
Festival Based Payment Promise
Payment Next Week
Payment Next Month
Settlement Request
Customer Requested Callback
Wrong Number
Family Member Answered
Silent Customer
Disconnected Call
Return ONLY valid JSON.
[
{{
    "conversation_id":123,
    "subgroup":"Payment Record Dispute"
}}
]
Conversations
{convo_block}
"""
    print(">>> Calling LLM...")
    response = _call_llm(prompt, max_tokens=500)
    print(">>> LLM returned")

    raw = (response.choices[0].message.content or "").strip()

    try:
        return json.loads(_extract_json(raw))
    except Exception:
        print(f"    [discover_subgroups] failed to parse, raw={raw!r}")
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

Analyze them deeply, but be CONCISE. Keep every string field short
(1 sentence max). This is a hard constraint.

Return ONLY valid JSON, no markdown fences, matching this exact shape.
Do not exceed these list lengths: common_patterns max 3 items,
breakdown max 3 items, insights max 3 items.

{{
"summary":"one sentence",

"customer_behavior":"one sentence",

"payment_intent":"High/Medium/Low",

"common_patterns":[
"short phrase",
"short phrase"
],

"breakdown":[
{{
"name":"...",
"description":"one short phrase",
"count":0
}}
],

"insights":[
"short phrase",
"short phrase"
]
}}

Conversations

{convo_text}
"""

    # Mentor wants max_tokens kept under 512. The old unbounded prompt
    # ("...", "...") let the LLM ramble past that and get truncated mid-JSON,
    # which fails json.loads() even with fence-stripping. Fix is a tighter
    # prompt (capped array lengths, "1 sentence max") rather than more tokens.
    response = _call_llm(prompt, max_tokens=500) 

    raw = (response.choices[0].message.content or "").strip()

    try:
        return json.loads(_extract_json(raw))
    except Exception:
        print(f"    [analyze_subgroup] failed to parse, raw={raw!r}")
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

    print(json.dumps(response, indent=2, ensure_ascii=False))
    return response