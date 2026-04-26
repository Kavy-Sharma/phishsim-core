# ai_engine/email_gen.py
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


def generate_phishing_email(employee_profile, scenario):
    """
    Takes employee profile dict + scenario string.
    Returns dict: {subject, sender_name, body_html}
    """

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

CRITICAL RULES:
- Do NOT hallucinate random sender names (like 'Jordan Lee' or 'John Doe').
- Sign off using ONLY the Department name (e.g., 'Human Resources', 'IT Support Team', or 'Finance Department').
- Make sure the tone matches the company context provided.

Return ONLY this JSON structure with no extra text, no markdown, no explanation:
{{"subject": "...", "sender_name": "...", "body_html": "..."}}"""

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
            return {
                "subject": "Action Required: Urgent Account Verification",
                "sender_name": "IT Security Team",
                "body_html": f"<p>Dear {employee_profile['name']},</p><p>We detected unusual login activity on your account. Please verify your credentials immediately to prevent account suspension.</p><p><a href='TRACKING_LINK'>Verify Account Now</a></p><p>Thank you,<br>IT Security Team</p>"
            }

    # --- If both attempts returned empty ---
    if not raw or not raw.strip():
        print("Model returned empty response after 2 attempts.")
        return {
            "subject": "Action Required: Urgent Account Verification",
            "sender_name": "IT Security Team",
            "body_html": f"<p>Dear {employee_profile['name']},</p><p>We detected unusual login activity on your account. Please verify your credentials immediately to prevent account suspension.</p><p><a href='TRACKING_LINK'>Verify Account Now</a></p><p>Thank you,<br>IT Security Team</p>"
        }

    # --- Clean markdown fences ---
    raw = raw.replace("```json", "").replace("```", "").strip()

    # --- Extract JSON object from response ---
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group()
    else:
        print(f"No JSON found. Raw output:\n{raw}")
        return {
            "subject": "Security Notice",
            "sender_name": "IT Department",
            "body_html": raw
        }

    # --- Parse JSON safely ---
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}\nRaw: {raw}")
        return {
            "subject": "Security Notice",
            "sender_name": "IT Department",
            "body_html": raw
        }


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
