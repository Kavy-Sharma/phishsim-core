# osint/scraper.py
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import csv
import time
import os
import concurrent.futures
from urllib.parse import urljoin, urlparse

import urllib3
from bs4 import BeautifulSoup
import httpx

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _same_domain(url, domain):
    try:
        host = urlparse(url).netloc.lower()
        host = host.split(':')[0]  # strip port
        if host.startswith('www.'):
            host = host[4:]
        target = domain.lower()
        if target.startswith('www.'):
            target = target[4:]
        return host == target or host.endswith('.' + target)
    except Exception:
        return False


def get_page_source(domain):
    """Fetches page source using httpx, falls back to Jina AI if content is too thin."""
    url = f"https://{domain}"
    
    html = None
    direct_timeout = float(os.getenv("OSINT_DIRECT_TIMEOUT_SECONDS", "5"))
    fallback_timeout = float(os.getenv("OSINT_FALLBACK_TIMEOUT_SECONDS", "7"))

    try:
        with httpx.Client(verify=False, timeout=direct_timeout, follow_redirects=True) as client:
            response = client.get(url, headers=HEADERS)
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
        jina_headers = HEADERS.copy()
        jina_headers["X-Return-Format"] = "html"
        try:
            with httpx.Client(verify=False, timeout=fallback_timeout, follow_redirects=True) as client:
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
    soup = BeautifulSoup(html, "html.parser")

    # Thin content check (moved earlier for reuse)
    meta = soup.find("meta", {"name": "description"})
    has_meta = meta and meta.get("content")
    paragraphs = soup.find_all("p")
    has_paragraphs = len(paragraphs) >= 3

    blocked_keywords = [
        "verify you are human",
        "just a moment",
        "access denied",
        "not a robot",
        "security check"
    ]

    is_blocked_keyword = any(word in html.lower() for word in blocked_keywords)
    is_thin = not (has_meta and has_paragraphs)

    if is_blocked_keyword and is_thin:
        profile["blocked"] = True
        return profile

    # --- Company name ---
    raw_title = soup.title.text.strip() if soup.title and soup.title.text else ""
    profile["company_name"] = (
        raw_title.split("|")[0].split("-")[0].split(",")[0].strip() or "Unknown"
    )

    # --- Description (with fallback to first heading) ---
    if has_meta:
        profile["description"] = meta["content"]
    else:
        heading = soup.find(["h1", "h2"])
        if heading:
            profile["description"] = heading.get_text(strip=True)

    # --- Writing tone (checks p tags first, falls back to divs, then full body) ---
    texts = [
        p.get_text(strip=True)
        for p in paragraphs
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

    profile["links"] = list(links)[:25] # Expand to search subpages

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

    # --- Search for exposed emails on subpages (contact, about, etc.) ---
    subpage_keywords = ["about", "contact", "team", "staff", "privacy", "help", "support", "career"]
    subpages_to_crawl = []
    for link in profile["links"]:
        # Only crawl links from the same domain to prevent scraping third-party websites
        if _same_domain(link, domain):
            if any(kw in link.lower() for kw in subpage_keywords):
                subpages_to_crawl.append(link)
    
    # De-duplicate crawl candidates
    subpages_to_crawl = list(set(subpages_to_crawl))[:3]
    
    scraped_emails = set(filtered_emails)
    
    def fetch_subpage(page_url):
        try:
            print(f"OSINT Scraper crawling subpage: {page_url}")
            with httpx.Client(verify=False, timeout=4.0, follow_redirects=True) as client:
                res = client.get(page_url, headers=HEADERS)
                if res.status_code == 200:
                    return res.text
        except Exception as crawl_err:
            print(f"Error crawling subpage {page_url}: {crawl_err}")
        return None

    if subpages_to_crawl:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_subpage, url): url for url in subpages_to_crawl}
            done, not_done = concurrent.futures.wait(futures.keys(), timeout=6.0)
            
            for future in done:
                try:
                    sub_html = future.result()
                    if sub_html:
                        sub_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", sub_html)
                        for semail in sub_emails:
                            semail_lower = semail.lower()
                            if "example.com" in semail_lower or "email.com" in semail_lower:
                                continue
                            if any(ext in semail_lower for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".css", ".js", ".mp4", ".webm"]):
                                continue
                            if not re.search(r"\.(com|org|net|edu|in|co)$", semail_lower):
                                continue
                            scraped_emails.add(semail)
                except Exception as fut_err:
                    print(f"Subpage future resolution error: {fut_err}")

    profile["emails"] = list(scraped_emails)[:10]

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
