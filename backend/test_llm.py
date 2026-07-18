import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("MRAKYTICS_LLM_API_KEY"),
    base_url=os.getenv("MRAKYTICS_LLM_BASE_URL"),
    timeout=150.0,
)

# your existing single transcript, kept exactly as-is
transcript = """Conversation ID: {n}
Transcript:
{"eoc": 1, "conversation": [{"name": "Nidhi", "type": "voicebot", "sender": "Bot", "message": "नमस्कार मे वेदिका फायनॅन्स से बोल रही हू. क्या नेरी बात najrana khatun जी से हो रही है ?", "response_type": "text"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ, हाँ।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Najrana ji, aapke e-rickshaw loan par ₹6792 ka overdue hai. Aapne ye payment due date ko kyun nahi ki?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "अरे भाई, बोलूँगा। बात करूँ ना?", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Mujhe maaf karna, main aapki baat samajh nahi paayi. Kya aap mujhe bata sakti hain ki aap payment kyun nahi kar payi?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ, हाँ, हम लोन पे लिए हुए हैं। आप बात करो ना हमसे।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main samajh sakti hoon ki kabhi-kabhi mushkil ho jaati hai. Kya aap mujhe bataengi ki aapko payment karne mein kya dikkat aa rahi hai?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हम पहले कहीं जा रहे हैं।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main aapki situation samajh sakti hoon. To aap ye payment kab tak karenge, ek tareekh bataiye?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हैं?", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Aapne koi date batayi thi? Main aapki payment ki date confirm karna chahti hoon.", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ, 2 तारीख का मेरा पेमेंट का लिखा हुआ था, और पेमेंट में पहुँचता था। वो जबरदस्ती बुला तो जानकर के नहीं किए, उसके बाद पेमेंट फिर पहुँचा करके आए हैं।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Mujhe lagta hai aapko thoda confusion ho raha hai. Aapne jo date batayi hai, kya aap mujhe aaj ya kal ki koi naye payment ki date bata sakti hain?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "मैं उसका एजेंसी बंद करवा दूँगा।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main aapki baat note kar rahi hoon. Lekin abhi ke liye, kya aap mujhe ek aisi date bata sakti hain jab aap yeh ₹6792 ka payment kar dengi?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Aapne koi specific date batayi hai jiske liye main note kar sakun?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "मैं 2 तारीख को पेमेंट, उसका पेमेंट करता हूँ। गाड़ी का एजेंसी में, जहाँ से गाड़ी लिया हूँ।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Aapne 2 तारीख ko payment karne ki baat ki hai. To maine note kar liya hai ki aap 2026-07-16 ko payment kar denge, ye sahi hai na?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "क्या- क्या बोले, फिर से बोलिए आप।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Maine kaha ki maine note kar liya hai ki aap 2026-07-16 ko payment kar denge, ye sahi hai na?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "नहीं, यह गलत है।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Agar 16 July sahi nahi hai, toh kya aap mujhe aaj ya kal ki koi aur date bata sakti hain jab aap payment kar payengi?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "नहीं, मैं पेमेंट कर दिया हूँ।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Agar aapne payment kar diya hai, toh kya aap mujhe transaction details share kar sakti hain taaki main agent se verify karwa sakun?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main aapki baat note kar rahi hoon. Agent verify karega.", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ। नोट कीजिए, मैम, आप नोट कीजिए।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main aapki baat note kar rahi hoon. Agent verify karega.", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "क्या?", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main keh rahi thi ki aapne payment kar diya hai, isliye main is baat ko agent se verify karwa rahi hoon. Kya aapko koi aur jaankari chahiye abhi?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "नाम?", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Mera naam Vedika hai, aur main Vedika Finance ki taraf se baat kar rahi hoon. Kya aapko is call ke baare mein koi aur sawaal hai?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हाँ, जी, हम समझ गए। मेरा काम— जी।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Agar aapko koi aur baat karni hai toh main sun rahi hoon. Kya hum is call ko yahan samapt kar sakte hain?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "सरकारी में बहुत कम है।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Main samajh sakti hoon ki aapki income ki situation mushkil ho sakti hai. Is situation mein, kya aap mujhe koi tentative date bata sakti hain jab aap payment karne ki koshish karengi?", "response_type": "audio"}, {"name": "najrana khatun", "type": "voicebot", "sender": "customer", "message": "हम्म।", "response_type": "audio"}, {"name": "Nidhi", "type": "voicebot", "sender": "bot", "message": "Kya aap mujhe koi aisi date bata sakti hain jo aapke liye possible ho, taaki hum us par note kar sakein?", "response_type": "audio"}"""

# build an 8-conversation batch, matching your real discovery_batch_size=8
num_conversations = 8
convo_block = "\n\n".join(
    transcript.replace("{n}", str(i)) for i in range(1, num_conversations + 1)
)

big_prompt = f"""You are a Senior QA Analyst for an EMI Recovery Voicebot (Hinglish calls).

Read the conversations below and identify the DISTINCT, RECOGNIZABLE patterns
of customer behaviour or situation actually present in THIS batch.

Return ONLY valid JSON, no markdown, no extra text:
[
  {{"name": "short label (2-5 words)", "description": "one sentence describing this pattern"}}
]

Conversations:

{convo_block}
"""

print(f"Prompt length: {len(big_prompt)} chars, {num_conversations} conversations")

start = time.time()
resp = client.chat.completions.create(
    model="google/gemma-4-E4B-it",
    max_tokens=600,
    messages=[{"role": "user", "content": big_prompt}],
    timeout=600.0,
)
print("Took", time.time() - start, "seconds")
print(resp.choices[0].message.content)