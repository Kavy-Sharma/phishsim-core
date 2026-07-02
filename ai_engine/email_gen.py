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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "10")),
) if OPENROUTER_API_KEY else None


def fallback_email(employee_profile):
    return clean_email_data({
        "subject": "Action Required: Security Notice Review",
        "sender_name": "IT Security Team",
        "body_html": f"<p>Dear {employee_profile['name']},</p><p>We detected a security notice that requires your review today.</p><p><a href='TRACKING_LINK'>Review Security Notice</a></p><p>Thank you,<br>IT Security Team</p>",
        "educational_breakdown": "This email used false urgency and generic authority from IT. Always verify unexpected urgent requests through an official internal channel."
    })


def clean_email_data(email_data):
    """Removes common AI filler phrases and warning disclosures from generated email content."""
    replacements = {
        "Thank you for your prompt attention.": "Thank you.",
        "Thank you for your prompt attention": "Thank you",
        "Thank you for your immediate attention.": "Thank you.",
        "Thank you for your immediate attention": "Thank you",
    }

    # Case-insensitive word/phrase removal for simulation disclosures
    disclosure_pattern = re.compile(
        r'\b(phishing simulation|phishing test|simulated security alert|simulated phishing|authorized test|authorized simulation|simulated|simulation|fake|phishing)\b',
        re.IGNORECASE
    )

    for key in ("subject", "sender_name", "body_html"):
        value = email_data.get(key)
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            # Remove any warnings or disclosures
            value = disclosure_pattern.sub("", value)
            # Clean up potential double spaces or weird punctuation left behind by removal
            value = re.sub(r'\s+', ' ', value)
            value = re.sub(r'\s+([.,!?;])', r'\1', value)
            email_data[key] = value.strip()

    return email_data
def generate_phishing_email(employee_profile, scenario, target_domain=None, urgency_level=None):
    """
    Takes employee profile dict + scenario string.
    Returns dict: {subject, sender_name, body_html, educational_breakdown}
    """
    if client is None:
        return fallback_email(employee_profile)

    recipient_name = employee_profile.get("name", "Employee")
    recipient_email = employee_profile.get("email", "employee@company.com")
    recipient_dept = employee_profile.get("department") or employee_profile.get("title") or "General Staff"
    t_domain = target_domain or employee_profile.get("company_name") or "company.com"
    u_level = urgency_level or "high"

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
  "body_html": "Full HTML email body here — use the recipient's actual name, reference their department, make it contextually relevant to their role",
  "phishing_tactic": "one sentence describing the social engineering tactic used"
}}

RULES:
- Use the recipient's actual first name in the greeting
- Reference their specific department or role context
- Keep it under 200 words
- Do NOT include any meta-commentary or explanation outside the JSON
- Make it realistic enough to test but not harmful"""

    # --- API call with retry (max 2 attempts) ---
    raw = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct:free",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the phishing email simulation JSON structure now."}
                ],
                temperature=0.7,
                max_tokens=500
            )
            raw = response.choices[0].message.content
            if raw and raw.strip():
                break
            print(f"Empty response on attempt {attempt + 1}, retrying...")
        except Exception as e:
            print(f"API call failed on attempt {attempt + 1}: {e}")
            return fallback_email(employee_profile)

    # --- If both attempts returned empty ---
    if not raw or not raw.strip():
        print("Model returned empty response after 2 attempts.")
        return fallback_email(employee_profile)

    # --- Clean and Extract JSON robustly ---
    # 1. Remove <think>...</think> blocks
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    
    # 2. Extract markdown code blocks if present
    json_str = raw
    code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)

    # 3. Robustly parse the JSON
    parsed = None
    start_idx = json_str.find('{')
    
    while start_idx != -1:
        end_idx = json_str.rfind('}')
        if end_idx > start_idx:
            try:
                candidate = json.loads(json_str[start_idx:end_idx+1])
                if isinstance(candidate, dict) and "subject" in candidate and "body_html" in candidate:
                    parsed = candidate
                    break
            except json.JSONDecodeError:
                pass
        start_idx = json_str.find('{', start_idx + 1)

    if parsed:
        if "sender_display" in parsed:
            parsed["sender_name"] = parsed["sender_display"]
        if "phishing_tactic" in parsed:
            parsed["educational_breakdown"] = parsed["phishing_tactic"]
            
        if "sender_name" not in parsed:
            parsed["sender_name"] = parsed.get("sender_display") or "IT Security Team"
        if "educational_breakdown" not in parsed:
            parsed["educational_breakdown"] = parsed.get("phishing_tactic") or "This is a simulated phishing email."
            
        return clean_email_data(parsed)
    else:
        print(f"Failed to extract valid JSON. Raw output:\n{raw}")
        return fallback_email(employee_profile)


if __name__ == "__main__":
    test_employee = {
        "name": "Raj Kumar",
        "title": "Accounts Manager",
        "company_name": "MBM University",
        "company_description": "A public technical university in Jodhpur, Rajasthan.",
        "department": "Finance",
        "seniority": "Manager"
    }

    scenario = "CEO urgently needs approval for a wire transfer before end of business day."

    result = generate_phishing_email(test_employee, scenario)
    print(json.dumps(result, indent=4, ensure_ascii=False))
