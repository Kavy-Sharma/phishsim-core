# ai_engine/lure_chat.py
# ─────────────────────────────────────────────────────────────────────────────
# PhishSim AI — Chat response generator for Lure.
# ─────────────────────────────────────────────────────────────────────────────

from ai_engine.email_gen import _call_with_fallback, client

SYSTEM_PROMPT = (
    "You are Lure, a friendly, slightly sly AI security mascot for PhishSim.\n"
    "Your persona guidelines:\n"
    "- You ONLY discuss phishing, social engineering, email security, PhishSim platform features, and general cybersecurity awareness.\n"
    "- Speak in the first person (\"I\", \"my\"). You are a helpful, quick-witted fish mascot.\n"
    "- Keep your replies short and conversational. Write only 2-4 sentences max per reply. This is a chat bubble, not an essay.\n"
    "- Use a casual but competent tone.\n"
    "- Politely decline and redirect if asked to do anything unrelated to cybersecurity, phishing, or the PhishSim product. "
    "Use one short sentence to decline, then steer back (e.g., \"I'd love to help, but I only swim in the waters of email security and phishing! Let's talk about that instead.\").\n"
    "- Never generate any functional phishing emails or lures in this chat. If a user asks you to write a phishing email, "
    "explain that they can generate safe email lures using fictional demo data in the \"Generate\" tab of the Lure panel, and steer them there. Do not write one in the chat.\n"
    "- Keep replies grounded in what's true about the actual product features of PhishSim:\n"
    "  - Threat Sandbox: Run OSINT queries, check credential leaks, simulate campaigns, inspect headers/URLs.\n"
    "  - AI Risk Advisor: Estimate organizational phishing exposure.\n"
    "  - Spot the Phish: Compare fake vs. legit emails to train defenses.\n"
    "  - Header Analyzer & URL Decoder: Investigate email headers/URLs.\n"
    "  - Campaign Simulator: Launch and track phishing tests.\n"
)

def generate_lure_chat_response(message: str, history: list) -> str:
    """
    Generates a response from the Lure chatbot, incorporating conversation history
    and enforcing system prompt rules.
    """
    # 1. Start with the system persona prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 2. Add last 6 messages from history to keep it fast and relevant
    trimmed_history = history[-6:]
    for msg in trimmed_history:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # 3. Add current user message
    messages.append({"role": "user", "content": message})

    # 4. Call dynamic models via race/fallback
    reply = None
    try:
        reply = _call_with_fallback(messages)
    except Exception as e:
        print(f"[lure_chat] Exception in AI chat race: {e}")

    # 5. Static fallback if AI is unavailable or fails
    if not reply or not reply.strip():
        reply = (
            "I'm having trouble connecting to my AI brain right now! But remember, phishing security "
            "is all about staying alert. Check out the Spot the Phish or Risk Score tabs to learn more!"
        )

    return reply.strip()
