import os, sys, requests, re
sys.path.insert(0, os.path.abspath('.'))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={'width': 375, 'height': 812})
    s = requests.Session()
    r = s.get('http://127.0.0.1:5050/login')
    csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
    token = csrf.group(1) if csrf else ''
    s.post('http://127.0.0.1:5050/login', data={'email': 'test_admin@phishsim.ai', 'password': 'TestPass123!', 'csrf_token': token})
    cookie = s.cookies.get('session')
    if cookie:
        ctx.add_cookies([{'name': 'session', 'value': cookie, 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx.new_page()
    urls = [
        ('login', 'http://127.0.0.1:5050/login'),
        ('dashboard', 'http://127.0.0.1:5050/dashboard'),
        ('new-campaign', 'http://127.0.0.1:5050/new-campaign'),
        ('billing', 'http://127.0.0.1:5050/billing'),
        ('admin', 'http://127.0.0.1:5050/admin'),
        ('users', 'http://127.0.0.1:5050/users'),
        ('reports/demo', 'http://127.0.0.1:5050/reports/demo')
    ]
    for name, url in urls:
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(300)
        sw = page.evaluate('document.documentElement.scrollWidth')
        cw = page.evaluate('document.documentElement.clientWidth')
        overflow = sw - cw
        status = "FAIL" if overflow > 0 else "PASS"
        print(f"[{status}] {name:15}: scrollWidth={sw}, clientWidth={cw}, overflow={overflow}px")
        if overflow > 0:
            # Find which elements exceed clientWidth
            culprits = page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('*'));
                const wide = [];
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    if (rect.right > 375.5) {
                        wide.push({
                            tag: el.tagName,
                            id: el.id,
                            cls: el.className,
                            right: rect.right,
                            width: rect.width
                        });
                    }
                }
                return wide.slice(0, 5);
            }""")
            print(f"   Culprits: {culprits}")
    browser.close()
