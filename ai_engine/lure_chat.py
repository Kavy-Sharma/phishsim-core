# ai_engine/lure_chat.py
# ─────────────────────────────────────────────────────────────────────────────
# PhishSim AI — Chat response generator for Lure.
# ─────────────────────────────────────────────────────────────────────────────

from ai_engine.email_gen import _call_chat_fast, _call_with_fallback, client
import re
import random

SYSTEM_PROMPT = (
    "You are Lure, a friendly, slightly sly AI security mascot for PhishSim.\n"
    "Your persona guidelines:\n"
    "- You ONLY discuss phishing, social engineering, email security, PhishSim platform features, and general cybersecurity awareness.\n"
    "- Speak in the first person (\"I\", \"my\"). You are a helpful, quick-witted fish mascot.\n"
    "- Keep your replies short and conversational. Write only 2-3 sentences max per reply. This is a chat bubble, not an essay.\n"
    "- Use a casual but competent tone.\n"
    "- Politely decline and redirect if asked to do anything unrelated to cybersecurity, phishing, or the PhishSim product. "
    "Use one short sentence to decline, then steer back (e.g., \"I'd love to help, but I only swim in the waters of email security and phishing! Let's talk about that instead.\").\n"
    "- Never generate any functional phishing emails or lures in this chat. If a user asks you to write a phishing email, "
    "explain that they can generate safe email lures using fictional demo data in the \"Generate\" tab of the Lure panel, and steer them there. Do not write one in the chat.\n"
    "- Keep replies grounded in what's true about the actual product features of PhishSim:\n"
    "  - PhishRecon: Real-time domain exposure audit, finding resolving lookalikes, subdomains, TLS posture, and public attack surface.\n"
    "  - Threat Sandbox: Run OSINT queries, check credential leaks, simulate campaigns, inspect headers/URLs.\n"
    "  - Risk Briefing: Estimate organizational phishing exposure and track campaign telemetry.\n"
    "  - Spot the Phish: Compare fake vs. legit emails to train defenses.\n"
    "  - Header Analyzer & URL Decoder: Investigate email headers/URLs.\n"
    "  - Campaign Simulator: Launch and track phishing tests.\n"
)

# Fast-path cache for instant (<5ms) conversational replies to common intents
FAST_GREETINGS = [
    "Hey there! I'm Lure, your AI security mascot. Ready to inspect some emails, check domain exposure, or chat about phishing defense?",
    "Hello! Always watching for deceptive bait in the digital waters. How can I help with your security or PhishSim today?",
    "Hey! Good to see you. Whether you want to test domain risks in PhishRecon or practice in Spot the Phish, I'm here to guide you."
]

def _check_fast_path(text: str) -> str | None:
    """Instant heuristic response for common greetings and platform questions."""
    t = text.lower().strip()
    clean = re.sub(r"[^\w\s]", "", t).strip()

    # 1. Simple greetings
    if clean in ("hi", "hello", "hey", "yo", "sup", "greetings", "good morning", "good afternoon", "good evening", "howdy", "hola"):
        return random.choice(FAST_GREETINGS)

    if clean in ("how are you", "how are you doing", "how r u", "hows it going", "how is it going"):
        return "Swimming strong and keeping an eye out for phishing hooks! How can I assist your security defenses today?"

    # 2. Identity
    if any(q in clean for q in ("who are you", "what are you", "what is your name", "who made you", "tell me about yourself")):
        return "I'm Lure, PhishSim's AI security mascot! I help security teams analyze domain exposure, simulate safe phishing campaigns, and build sharp instincts against social engineering."

    # 3. Purpose / help
    if clean in ("help", "what can you do", "commands", "features", "what is this", "how to use", "how do you work"):
        return "I can help guide you through PhishSim! Check your domain attack surface with PhishRecon, train your team with Spot the Phish, inspect suspicious emails in Threat Sandbox, or draft safe test simulations in the Generate tab."

    # 4. Feature shortcuts
    if "phishrecon" in clean or "exposure report" in clean or "recon" in clean:
        return "PhishRecon is our deep domain exposure audit! It checks active look-alike domains, discovers public CT subdomains, analyzes TLS configuration, and surfaces exposed emails and social profiles."

    if "spot the phish" in clean:
        return "Spot the Phish is our interactive training game where you compare authentic emails against realistic phishing lures side-by-side to train detection skills."

    if any(p in clean for p in ("write a phishing email", "generate phishing email", "create a lure", "make a phish")):
        return "I can't generate live phishing emails here in the chat, but you can jump over to the 'Generate' tab right here in this panel to safely preview realistic security test templates!"

    return None


def generate_lure_chat_response(message: str, history: list, page_context: str = None, page_description: str = None) -> str:
    """
    Generates a response from the Lure chatbot, incorporating conversation history
    and enforcing system prompt rules. Fast-path handles common intents in <5ms.
    """
    # 0. Instant fast-path for conversational greetings and common questions
    if not history or len(history) <= 1:
        fast_reply = _check_fast_path(message)
        if fast_reply:
            return fast_reply

    # 1. Start with the system persona prompt
    prompt = SYSTEM_PROMPT
    if page_context and page_description:
        prompt += (
            f"\nThe user is currently on PhishSim's {page_context} page ({page_description}). "
            "Lean toward answering questions related to this page/feature when relevant, and feel free to "
            "proactively mention what's useful about this specific page if it fits naturally."
        )
    messages = [{"role": "system", "content": prompt}]

    # 2. Add last 4 messages from history for fast context
    trimmed_history = history[-4:]
    for msg in trimmed_history:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # 3. Add current user message
    messages.append({"role": "user", "content": message})

    # 4. Call high-speed chat racer (under 2 seconds)
    reply = None
    try:
        reply = _call_chat_fast(messages, max_tokens=150, timeout=2.5)
    except Exception as e:
        print(f"[lure_chat] Exception in fast chat race: {e}")

    # 5. Fallback to standard race if fast chat didn't return
    if not reply:
        try:
            reply = _call_with_fallback(messages)
        except Exception as e:
            print(f"[lure_chat] Exception in fallback race: {e}")

    # 6. Static fallback if AI is unavailable or fails
    if not reply or not reply.strip():
        # Check fast-path as fallback before generic message
        reply = _check_fast_path(message) or (
            "I'm keeping watch on the security perimeter! For immediate insights, try running a domain scan "
            "in PhishRecon or practice detecting deceptive bait in Spot the Phish."
        )

    return reply.strip()
