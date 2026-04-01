import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
from osint.scraper import scrape_company, build_employee_profiles
from ai_engine.email_gen import generate_phishing_email
from ai_engine.scenarios import SCENARIOS

# Step 1 — Get company profile (no API call, just scraping)
company = scrape_company("mbmiums.in")

# Step 2 — Build employee profiles from CSV
employees = build_employee_profiles("data/test_employees.csv", company)

# Step 3 — Generate one email per employee with different scenarios
scenario_keys = ["ceo_fraud", "it_alert", "hr_update"]

for i, emp in enumerate(employees):
    scenario = SCENARIOS[scenario_keys[i]]
    print(f"\n--- Email for {emp['name']} ({emp['department']}) ---")
    result = generate_phishing_email(emp, scenario)
    print(json.dumps(result, indent=4, ensure_ascii=False))