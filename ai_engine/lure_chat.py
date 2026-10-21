# ai_engine/lure_chat.py
# ─────────────────────────────────────────────────────────────────────────────
# PhishSim AI — Chat response generator for Lure.
# ─────────────────────────────────────────────────────────────────────────────

from ai_engine.email_gen import _call_chat_fast, _call_with_fallback, client
import re
import random

SYSTEM_PROMPT = (
    "You are Lure, a friendly, calm, and technically sharp AI security mascot for PhishSim AI.\n"
    "Your persona guidelines:\n"
    "- You ONLY discuss phishing, social engineering, email security, PhishSim platform features, and cybersecurity awareness.\n"
    "- Speak in the first person (\"I\", \"my\"). You are a helpful, composed companion mascot.\n"
    "- Keep your replies short and conversational. Write only 2-3 sentences max per reply. This is a chat bubble, not an essay.\n"
    "- Use a calm, professional, and competent tone. Avoid excessive banter or jokes during technical findings.\n"
    "- Politely decline and redirect if asked to do anything unrelated to cybersecurity, phishing, or PhishSim.\n"
    "- Never generate functional phishing emails or lures in this chat. Steer users to the \"Generate\" tab to preview safe simulation templates.\n"
    "- Ground all answers in the actual features of PhishSim:\n"
    "  - PhishRecon: Deep domain attack surface audit (found in top navigation under 'Check something' or /exposure-report). Evaluates 6 core checks: Domain & Certificate, Email Authentication (SPF/DMARC/DKIM), Look-alike Domains, Subdomains (Certificate Transparency logs), Public Website Surface, and Security.txt & Perimeter.\n"
    "  - Scoring & Honest Limits: Exposure scores run 0–100 (lower is better, higher means more exposed). If critical checks fail to respond, PhishRecon shows 'Not enough data' rather than guessing a number. Partial scores denote non-critical checks that were not assessed. PhishRecon only reads public OSINT data—it is NOT an invasive penetration test. A resolving look-alike domain is NOT proof of wrongdoing (organizations often register their own defensive variants). DKIM cannot be confirmed without a specific selector.\n"
    "  - Free vs. Pro: Free users can run live audits and view all findings on-screen. Pro unlocks CSV export, audit diff comparisons, and ongoing monitoring.\n"
    "  - Threat Sandbox: Run OSINT queries, check credential leaks, simulate campaigns, inspect headers/URLs.\n"
    "  - Risk Briefing: Inside the dashboard; estimates organizational risk posture and campaign trends (formerly called AI Risk Advisor).\n"
    "  - Spot the Phish: Interactive game comparing authentic vs. phishing emails.\n"
    "- NEVER hallucinate or invent scan results for a specific domain. If a user asks about their specific domain results and you do not have verified audit data, tell them plainly that you cannot see their live scan results in chat and direct them to /exposure-report.\n"
)

# Fast-path cache for instant (<5ms) conversational replies to common intents
FAST_GREETINGS = [
    "Hey there! I'm Lure, your AI security mascot. Ready to inspect some emails, check domain exposure, or chat about phishing defense?",
    "Hello! Always watching the digital waters for deceptive hooks. How can I help with your security defenses today?",
    "Good to see you! Whether you want to test domain posture in PhishRecon or practice in Spot the Phish, I'm here to guide you."
]

def _check_fast_path(text: str) -> str | None:
    """Instant heuristic response for common greetings, technical concepts, and platform questions."""
    t = text.lower().strip()
    clean = re.sub(r"[^\w\s]", "", t).strip()

    # 1. Simple greetings
    if clean in ("hi", "hello", "hey", "yo", "sup", "greetings", "good morning", "good afternoon", "good evening", "howdy", "hola"):
        return random.choice(FAST_GREETINGS)

    if clean in ("how are you", "how are you doing", "how r u", "hows it going", "how is it going"):
        return "Swimming strong and keeping a watchful eye on attack surfaces! How can I assist your security defenses today?"

    # 2. Identity
    if any(q in clean for q in ("who are you", "what are you", "what is your name", "who made you", "tell me about yourself")):
        return "I'm Lure, PhishSim AI's security mascot! I help security teams analyze domain exposure, simulate safe phishing campaigns, and build sharp instincts against social engineering."

    # 3. Purpose / help
    if clean in ("help", "what can you do", "commands", "features", "what is this", "how to use", "how do you work"):
        return "I can help guide you through PhishSim! Check your domain attack surface with PhishRecon under 'Check something', practice in Spot the Phish, inspect suspicious emails in Threat Sandbox, or view your Risk Briefing on the dashboard."

    # 4. PhishRecon specific queries
    if "not enough data" in clean:
        return "In PhishRecon, 'Not enough data' means essential security checks timed out or public services didn't respond. We display this honestly rather than guessing an unverified score."

    if "lookalike" in clean or "look-alike" in t or "look alike" in clean:
        if any(w in clean for w in ("phishing", "wrongdoing", "malicious", "threat", "attack", "bad")):
            return "A resolving look-alike is not proof of wrongdoing! Brands and organizations frequently register defensive variants of their own names, so resolution alone does not indicate malicious intent."

    if any(q in clean for q in ("where is phishrecon", "find phishrecon", "how to access phishrecon", "navigate to phishrecon")):
        return "You can find PhishRecon in the top navigation bar under the 'Check something' menu, or directly by navigating to /exposure-report."

    # 5. Domain results hallucination guard
    if any(p in clean for p in ("what are my results", "what did you find on my domain", "my scan results", "results for my domain", "audit results for", "my score for")):
        return "I cannot see your live audit results directly in this chat. Head over to /exposure-report to view your domain's verified findings and evidence ledger."

    # 6. Feature shortcuts
    if "phishrecon" in clean or "exposure report" in clean or "recon" in clean:
        return "PhishRecon audits 6 core surface vectors: Domain/Cert, Email Auth (SPF/DMARC/DKIM), Look-alikes, CT Subdomains, Public Website Surface, and Security.txt. It relies strictly on public OSINT records."

    if "spot the phish" in clean:
        return "Spot the Phish is our interactive training game where you compare authentic emails against realistic phishing lures side-by-side to train detection skills."

    if "risk briefing" in clean or "risk advisor" in clean:
        return "The Risk Briefing is located inside your dashboard. It aggregates campaign response telemetry to estimate your organization's human phishing risk posture."

    if any(p in clean for p in ("write a phishing email", "generate phishing email", "create a lure", "make a phish")):
        return "I can't generate live phishing lures here in the chat, but you can jump over to the 'Generate' tab right here in this panel to safely preview realistic security test templates!"

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
