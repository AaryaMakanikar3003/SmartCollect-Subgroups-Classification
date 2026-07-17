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

All conversations below already belong to the SAME top-level category.

DO NOT classify the top-level category again.

Your task is to identify the SINGLE behavioural subgroup that BEST represents each conversation.

------------------------------------------------
IMPORTANT
------------------------------------------------

Read the ENTIRE conversation before making a decision.

Do NOT classify based only on the opening lines.

Conversations often evolve.

Customers may initially:

- deny identity
- question the caller
- appear confused
- say they already paid
- dispute the outstanding amount

but later move into a completely different discussion.

Your job is to identify the behaviour that DOMINATES the overall conversation.

------------------------------------------------
HOW TO CHOOSE THE SUBGROUP
------------------------------------------------

Ask yourself:

1. What occupied most of the conversation?

2. What issue did both customer and bot spend the most time discussing?

3. What is the customer's primary behaviour throughout the call?

4. If another analyst grouped similar conversations together, which subgroup would this conversation naturally belong to?

Choose the subgroup that best answers these questions.

------------------------------------------------
IMPORTANT GUIDELINES
------------------------------------------------

Temporary confusion at the beginning of the call should NOT determine the subgroup.

Examples of temporary behaviours:

- Wrong person
- Who are you?
- Which company?
- Who are you calling?
- Name verification
- Initial hesitation

If these are resolved and the conversation becomes a payment discussion, classify using the payment behaviour.

------------------------------------------------
WRONG NUMBER
------------------------------------------------

Use "Wrong Number" ONLY when:

- customer continuously denies being the borrower

AND

- the conversation never progresses into meaningful loan discussion.

Examples:

✓ Wrong number
✓ Call ends

✓ Wrong person
✓ Bot apologizes
✓ Call disconnected

These belong to Wrong Number.

DO NOT use Wrong Number if the customer later discusses:

- outstanding dues
- loan account
- payment history
- settlement
- payment date
- payment method
- repayment plan

Those conversations should be classified according to the dominant payment behaviour.

------------------------------------------------
PAYMENT RECORD DISPUTE
------------------------------------------------

Use this subgroup when the dominant discussion is about payment already made, missing payments, incorrect records, or disagreement about transaction history.

Even if the customer later promises to pay, the subgroup remains Payment Record Dispute if the dispute is the primary topic.

------------------------------------------------
PROMISE TO PAY
------------------------------------------------

Use Promise to Pay when the dominant behaviour is the customer's commitment to make payment.

Examples include:

- payment tomorrow
- payment next week
- payment after salary
- payment after festival
- payment on a specific date
- payment via UPI
- payment via bank transfer

Initial identity verification issues should be ignored if the majority of the conversation is about confirming payment.

------------------------------------------------
SUBGROUP NAMES
------------------------------------------------

Use short business-friendly names.

Examples:

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

Fraud / Scam Suspicion

Reuse existing subgroup names whenever possible.

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
You are a Senior QA Analyst reviewing debt collection conversations.

All conversations below already belong to ONE subgroup.

Subgroup:

{subgroup_name}

Your task is to perform a deep behavioural analysis.

---------------------------------------
VERY IMPORTANT
---------------------------------------

Do NOT create another top-level subgroup.

Instead analyse HOW conversations differ
inside this subgroup.

Think like an operations manager.

Example

Promise to Pay

↓

Tomorrow Payment

↓

UPI Payment Tomorrow

↓

Representative conversations

NOT

Promise to Pay

↓

Already Paid

↓

Wrong Number

Those are different subgroups.

---------------------------------------
STEP 1
---------------------------------------

Identify 4-8 meaningful behavioural buckets.

Every conversation MUST belong to exactly ONE bucket.

The bucket counts MUST sum exactly to the total number of conversations.

---------------------------------------
STEP 2
---------------------------------------

For every bucket identify 2-6 micro behaviours.

Micro behaviours are finer distinctions.

Example

Tomorrow Payment

↓

UPI

↓

Bank Visit

↓

Cash Payment

↓

Relative Will Pay

↓

Salary Tomorrow

---------------------------------------
STEP 3
---------------------------------------
For every micro behaviour:

• Describe the defining characteristics.

• Mention what kind of conversations belong here.

• DO NOT return conversation transcripts.

Representative conversations will be fetched separately by the application.

Only perform behavioural analysis.

---------------------------------------
OUTPUT

Return ONLY valid JSON.

{{
"summary":"...",

"customer_behavior":"...",

"payment_intent":"High/Medium/Low",

"common_patterns":[
"..."
],

"breakdown":[
{{
"name":"Tomorrow Payment",

"description":"Customer promises payment within one day.",

"count":32,

"sub_breakdown":[

{{
"name":"UPI Tomorrow",

"description":"Customer specifically mentions UPI payment.",

"count":9,
}},

{{
"name":"Bank Visit",

"description":"Customer will visit branch.",

"count":7,
}}

]
}}

],

"insights":[
"..."
]

}}

Rules

1. Every conversation must appear inside exactly ONE breakdown bucket.

2. Every conversation must appear inside exactly ONE sub_breakdown.

3. Sum of breakdown counts = total conversations.

4. Sum of sub_breakdown counts = parent breakdown count.

5. Do not invent statistics or counts.

6. Use business-friendly names.

7. Do not return conversation transcripts. They will be fetched separately by the application.

Conversations

{convo_text}
"""
    response = _call_llm(prompt, max_tokens=3000) 

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

    clusters = []

    for subgroup_name, subgroup_conversations in grouped.items():

        notify(f"Analyzing subgroup: {subgroup_name}")

        analysis = analyze_subgroup(
            subgroup_name,
            subgroup_conversations
        )
        
        print("\n========================")
        print("ANALYSIS FOR:", subgroup_name)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        print("========================\n")

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

    clusters.sort(key=lambda x: x["count"], reverse=True)

    response["categories"][category] = {
        "total": len(usable),
        "clusters": clusters
    }
 
    notify("Finished.")

    print(json.dumps(response, indent=2, ensure_ascii=False))
    return response