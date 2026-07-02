# ai_engine/email_gen.py
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── OpenRouter client ────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20")),
) if OPENROUTER_API_KEY else None

# Ordered fallback list — first model is attempted first; on 404/429/empty we
# advance to the next one automatically.
FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def fallback_email(employee_profile):
    return clean_email_data({
        "subject": "Action Required: Security Notice Review",
        "sender_name": "IT Security Team",
        "body_html": (
            f"<p>Dear {employee_profile.get('name', 'Employee')},</p>"
            "<p>We detected a security notice that requires your review today.</p>"
            "<p><a href='TRACKING_LINK'>Review Security Notice</a></p>"
            "<p>Thank you,<br>IT Security Team</p>"
        ),
        "educational_breakdown": (
            "This email used false urgency and generic authority from IT. "
            "Always verify unexpected urgent requests through an official internal channel."
        ),
    })


def clean_email_data(email_data):
    """Removes common AI filler phrases and simulation disclosures from generated content."""
    replacements = {
        "Thank you for your prompt attention.": "Thank you.",
        "Thank you for your prompt attention": "Thank you",
        "Thank you for your immediate attention.": "Thank you.",
        "Thank you for your immediate attention": "Thank you",
    }

    disclosure_pattern = re.compile(
        r'\b(phishing simulation|phishing test|simulated security alert|simulated phishing|'
        r'authorized test|authorized simulation|simulated|simulation|fake|phishing)\b',
        re.IGNORECASE,
    )

    for key in ("subject", "sender_name", "body_html"):
        value = email_data.get(key)
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            value = disclosure_pattern.sub("", value)
            value = re.sub(r'\s+', ' ', value)
            value = re.sub(r'\s+([.,!?;])', r'\1', value)
            email_data[key] = value.strip()

    return email_data


def _parse_json_response(raw: str):
    """Robustly extracts the first valid JSON object that has 'subject' and 'body_html' keys."""
    # Strip <think>…</think> blocks produced by some reasoning models
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

    # Unwrap markdown code fences if present
    json_str = raw
    code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if code_block:
        json_str = code_block.group(1)

    start = json_str.find('{')
    while start != -1:
        end = json_str.rfind('}')
        if end > start:
            try:
                candidate = json.loads(json_str[start:end + 1])
                if isinstance(candidate, dict) and "subject" in candidate and "body_html" in candidate:
                    return candidate
            except json.JSONDecodeError:
                pass
        start = json_str.find('{', start + 1)

    return None


# ─── Core generation with model fallback chain ────────────────────────────────
def _call_with_fallback(messages: list) -> str | None:
    """
    Tries each model in FREE_MODELS in order.
    Returns the raw string content on success, or None if all models fail.
    """
    if client is None:
        return None

    for model in FREE_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=600,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"[email_gen] Successfully used model: {model}")
                return content
            print(f"[email_gen] Model {model} returned empty content — trying next...")
        except Exception as exc:
            err_str = str(exc).lower()
            if "404" in err_str or "429" in err_str or "model" in err_str:
                print(f"[email_gen] Model {model} unavailable ({exc}) — trying next...")
                continue
            # Unexpected error — log and move on
            print(f"[email_gen] Model {model} raised unexpected error: {exc} — trying next...")
            continue

    print("[email_gen] All OpenRouter models exhausted — using static fallback.")
    return None


# ─── Public API ───────────────────────────────────────────────────────────────
def generate_phishing_email(employee_profile, scenario, target_domain=None, urgency_level=None):
    """
    Generates a realistic phishing email for a security awareness simulation.

    Args:
        employee_profile (dict): Keys: name, email, department, title, company_name, …
        scenario        (str):  Short scenario descriptor (e.g. 'it_alert', 'hr_update').
        target_domain   (str):  Target company domain override.
        urgency_level   (str):  'low' | 'medium' | 'high'.

    Returns:
        dict: {subject, sender_name, body_html, educational_breakdown}
    """
    if client is None:
        print("[email_gen] OPENROUTER_API_KEY not set — using static fallback.")
        return fallback_email(employee_profile)

    recipient_name  = employee_profile.get("name", "Employee")
    recipient_email = employee_profile.get("email", "employee@company.com")
    recipient_dept  = (
        employee_profile.get("department")
        or employee_profile.get("title")
        or "General Staff"
    )
    t_domain = target_domain or employee_profile.get("company_name") or "company.com"
    u_level  = urgency_level or "high"

    system_prompt = f"""You are a phishing email generator for authorized security training simulations.
Generate a realistic phishing email with these exact requirements:

RECIPIENT: {recipient_name} ({recipient_email})
ROLE/DEPARTMENT: {recipient_dept}
SCENARIO: {scenario}
TARGET COMPANY DOMAIN: {t_domain}
URGENCY LEVEL: {u_level}

OUTPUT FORMAT — respond with ONLY a JSON object, no markdown, no explanation:
{{
  "subject": "Email subject line here",
  "sender_display": "Sender Name Here",
  "body_html": "Full HTML email body — use the recipient's actual name, reference their department, make it contextually relevant to their role",
  "phishing_tactic": "one sentence describing the social engineering tactic used"
}}

RULES:
- Use the recipient's actual first name in the greeting
- Reference their specific department or role context
- Keep it under 200 words
- Do NOT include any meta-commentary or explanation outside the JSON
- Make it realistic enough to test but not harmful"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Generate the phishing email simulation JSON structure now."},
    ]

    raw = _call_with_fallback(messages)

    if not raw:
        return fallback_email(employee_profile)

    parsed = _parse_json_response(raw)

    if parsed:
        # Normalise field names
        if "sender_display" in parsed:
            parsed.setdefault("sender_name", parsed["sender_display"])
        if "phishing_tactic" in parsed:
            parsed.setdefault("educational_breakdown", parsed["phishing_tactic"])
        parsed.setdefault("sender_name", "IT Security Team")
        parsed.setdefault("educational_breakdown", "This is a simulated phishing email.")
        return clean_email_data(parsed)

    print(f"[email_gen] Failed to parse JSON from model response:\n{raw}")
    return fallback_email(employee_profile)


# ─── CLI smoke-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_employee = {
        "name":                "Raj Kumar",
        "title":               "Accounts Manager",
        "company_name":        "MBM University",
        "company_description": "A public technical university in Jodhpur, Rajasthan.",
        "department":          "Finance",
        "seniority":           "Manager",
    }
    scenario = "CEO urgently needs approval for a wire transfer before end of business day."
    result = generate_phishing_email(test_employee, scenario)
    print(json.dumps(result, indent=4, ensure_ascii=False))
