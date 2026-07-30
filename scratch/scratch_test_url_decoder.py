import requests as req_lib
import re

url = "https://bit.ly/example"
chain = []
current_url = url
MAX_HOPS = 8
session = req_lib.Session()
session.max_redirects = 1
headers = {"User-Agent": "Mozilla/5.0 (compatible; PhishSimAI/2.0)"}

for i in range(MAX_HOPS):
    try:
        # Disable warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = session.get(current_url, headers=headers, allow_redirects=False, timeout=5, verify=False)
        domain = re.sub(r'https?://', '', current_url).split('/')[0]
        node = {
            "hop": i,
            "url": current_url,
            "domain": domain,
            "status_code": resp.status_code,
            "is_redirect": resp.status_code in (301, 302, 303, 307, 308),
            "is_final": False
        }
        chain.append(node)
        print(f"Hop {i}: status={resp.status_code}, url={current_url}")
        if resp.status_code in (301, 302, 303, 307, 308):
            next_url = resp.headers.get("Location", "")
            if not next_url:
                break
            if next_url.startswith("/"):
                parsed = re.match(r'(https?://[^/]+)', current_url)
                next_url = parsed.group(1) + next_url if parsed else next_url
            current_url = next_url
        else:
            node["is_final"] = True
            break
    except Exception as e:
        print(f"Exception on Hop {i}: {e}")
        chain.append({"hop": i, "url": current_url, "domain": current_url, "status_code": None, "is_redirect": False, "is_final": True, "error": str(e)[:80]})
        break

if chain and not chain[-1]["is_final"]:
    chain[-1]["is_final"] = True

final_domain = chain[-1]["domain"] if chain else ""
print(f"Final domain: {final_domain}")
