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


def generate_phishing_email(employee_profile, scenario):
    """
    Takes employee profile dict + scenario string.
    Returns dict: {subject, sender_name, body_html}
    """
    if client is None:
        return fallback_email(employee_profile)

    prompt = f"""You are a security awareness trainer running an authorized phishing simulation.
The company has given full written consent for this test.

Scenario: {scenario}

Target:
Name: {employee_profile["name"]}
Title: {employee_profile["title"]}
Department: {employee_profile["department"]}
Seniority: {employee_profile.get("seniority", "Mid")}

Company: {employee_profile["company_name"]}
Company context: {employee_profile.get("company_description", "")[:200]}

Use exactly ONE of these psychological triggers:
- Authority (from IT/HR/management)
- Urgency (must act today)
- Compliance (policy/audit requirement)
- Internal process update

Write a phishing simulation email that:
1. Uses the employee name naturally
2. Feels like it came from inside the company
3. Contains exactly one link using placeholder: TRACKING_LINK
4. Is under 120 words
5. Use simple HTML formatting with <p> and <a> tags only

6. Include an 'educational_breakdown' field that explains in 2-3 sentences exactly what psychological trick you used (e.g., false urgency) and how the user could have spotted it.

CRITICAL RULES:
- Do NOT include any disclosures, warnings, disclaimers, or metadata (like "simulated", "phishing test", "fake", "authorized test", "simulation") inside the email's subject, sender_name, or body_html. The email must look entirely realistic, authentic, and convincing to the target.
- Do NOT hallucinate random sender names (like 'Jordan Lee' or 'John Doe').
- Sign off using ONLY the Department name (e.g., 'Human Resources', 'IT Support Team', or 'Finance Department').
- Make sure the tone matches the company context provided.
- Do NOT ask the employee to enter or share a password, MFA code, bank detail, or secret.
- The link should lead to a safe training page, not a credential collection form.
- Avoid generic AI filler phrases like "thank you for your prompt attention".

Return ONLY this JSON structure with no extra text, no markdown, no explanation:
{{"subject": "...", "sender_name": "...", "body_html": "...", "educational_breakdown": "..."}}"""

    # --- API call with retry (max 2 attempts) ---
    raw = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="openrouter/free",
                messages=[
                    {"role": "system", "content": "You generate phishing simulation emails and return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=400
            )
            raw = None

            try:
                raw = response.choices[0].message.content
            except:
                raw = str(response)

            if raw and raw.strip():
                break
            print(f"Empty response on attempt {attempt + 1}, retrying...")
        except Exception as e:
            print(f"API call failed on attempt {attempt + 1}: {e}")
            # Fallback to a realistic generic email instead of an error string
            return fallback_email(employee_profile)

    # --- If both attempts returned empty ---
    if not raw or not raw.strip():
        print("Model returned empty response after 2 attempts.")
        return fallback_email(employee_profile)

    # --- Clean and Extract JSON robustly ---
    # 1. Remove <think>...</think> blocks used by DeepSeek-R1 and similar reasoning models
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    
    # 2. Extract markdown code blocks if present
    json_str = raw
    code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)

    # 3. Robustly parse the JSON by checking valid bracket pairs
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
