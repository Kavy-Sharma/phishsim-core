# osint/scraper.py
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import csv
import time
from urllib.parse import urljoin

import urllib3
from bs4 import BeautifulSoup
import httpx

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_page_source(domain):
    """Fetches page source using httpx, falls back to Jina AI if content is too thin."""
    url = f"https://{domain}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    html = None
    try:
        with httpx.Client(verify=False, timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        print(f"httpx direct fetch error: {e}")
        
    needs_fallback = False
    if not html:
        needs_fallback = True
    else:
        soup = BeautifulSoup(html, "html.parser")
        meta_desc = soup.find("meta", {"name": "description"})
        paragraphs = soup.find_all("p")
        
        has_meta = meta_desc and meta_desc.get("content")
        has_paragraphs = len(paragraphs) >= 3
        
        if not has_meta and not has_paragraphs:
            needs_fallback = True
            
    if needs_fallback:
        print(f"Content thin or request failed for {domain}, falling back to Jina AI...")
        jina_url = f"https://r.jina.ai/{url}"
        jina_headers = headers.copy()
        jina_headers["X-Return-Format"] = "html"
        try:
            with httpx.Client(verify=False, timeout=20.0, follow_redirects=True) as client:
                response = client.get(jina_url, headers=jina_headers)
                response.raise_for_status()
                html = response.text
        except Exception as e:
            print(f"Jina AI fallback error: {e}")

    return html


def scrape_company(domain):
    """Scrapes public company info from their website. Returns a profile dict."""
    profile = {
        "domain": domain,
        "company_name": "",
        "description": "",
        "recent_context": [],
        "writing_tone": "",
        "emails": [],
        "links": [],
        "socials":{}
    }

    html = get_page_source(domain)
    if not html:
        return profile
    blocked_keywords = [
    "verify you are human",
    "just a moment",
    "access denied",
    "not a robot",
    "security check"
    ]

    if any(word in html.lower() for word in blocked_keywords):
        profile["blocked"] = True
        return profile
    soup = BeautifulSoup(html, "html.parser")

    # --- Company name ---
    profile["company_name"] = (
        soup.title.text.split("|")[0].split("-")[0].split(",")[0].strip()
        if soup.title else "Unknown"
    )

    # --- Description (with fallback to first heading) ---
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        profile["description"] = meta["content"]
    else:
        heading = soup.find(["h1", "h2"])
        if heading:
            profile["description"] = heading.get_text(strip=True)

    # --- Writing tone (checks p tags first, falls back to divs, then full body) ---
    texts = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 20
    ]

    if not texts:
        texts = [
            div.get_text(strip=True)
            for div in soup.find_all("div")
            if len(div.get_text(strip=True)) > 50
        ]

    if not texts:
        body_text = soup.get_text(separator=" ", strip=True)
        texts = [body_text[:500]]

    profile["writing_tone"] = " ".join(texts[:3])[:500]

    # --- Emails (filtered to remove image/CSS file false positives) ---
    raw_emails = set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html))

    filtered_emails = []
    
    for email in raw_emails:
        email_lower = email.lower()

        if "example.com" in email_lower:
            continue

        if "email.com" in email_lower:
            continue
        
        if any(ext in email_lower for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".css", ".js", ".mp4", ".webm"]):
            continue
        
        if not re.search(r"\.(com|org|net|edu|in|co)$", email_lower):
            continue
        
        filtered_emails.append(email)

    profile["emails"] = filtered_emails[:5]

    # Links
    links = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href")

        if not href or href == "#":
            continue

        if href.startswith("javascript:"):
            continue

        href = href.replace("\\", "/")
        full_url = urljoin(f"https://{domain}", href)
        links.add(full_url)

    profile["links"] = list(links)[:10]

    social_patterns = {
        "linkedin": "linkedin.com",
        "twitter": "twitter.com",
        "youtube": "youtube.com",
        "facebook": "facebook.com",
        "instagram": "instagram.com"
    }

    socials = {}

    for link in profile["links"]:
        for name, pattern in social_patterns.items():
            if pattern in link:
                socials[name] = link

    profile["socials"] = socials

    # --- Recent context (headlines from articles or headings) ---
    articles = soup.find_all("article")
    headlines = []

    for article in articles:
        h = article.find(["h1", "h2", "h3"])
        if h and len(h.get_text(strip=True)) > 20:
            headlines.append(h.get_text(strip=True))

    if not headlines:
        headlines = [
            tag.get_text(strip=True)
            for tag in soup.find_all(["h1", "h2", "h3"])
            if len(tag.get_text(strip=True)) > 15
        ]

    news_links = [
        link for link in profile["links"]
        if any(word in link.lower() for word in [
            "news", "article", "blog", "press", "update"
        ])
    ]
    profile["recent_context"] = headlines[:3] + news_links[:2]

    return profile


def build_employee_profiles(csv_path, company_profile):
    """Reads employee CSV and combines each row with company context."""
    employees = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profile = {
                "name": row["name"],
                "email": row["email"],
                "department": row["department"],
                "title": row["title"],
                "seniority": row.get("seniority", "Mid"),  # default to Mid if missing
                "company_name": company_profile["company_name"],
                "company_description": company_profile["description"],
                "company_tone": company_profile["writing_tone"]
            }
            employees.append(profile)
    
    return employees


if __name__ == "__main__":
    company = scrape_company("google.com")
    print(json.dumps(company, indent=4, ensure_ascii=False))
    print("---")
    employees = build_employee_profiles("data/test_employees.csv", company)
    print(json.dumps(employees, indent=4, ensure_ascii=False))