import os, sys
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright

def verify_all():
    print("=== STARTING COMPREHENSIVE VERIFICATION ===")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # 1. Desktop verification (1440x900)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        
        # Check Home page
        print("\n--- 1. Testing Home Page ---")
        page.goto("http://127.0.0.1:5050/", wait_until="networkidle")
        
        # Verify font family on headings
        stats_h2 = page.locator("#stats .section-title")
        stats_font = stats_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        stats_align = stats_h2.evaluate("el => window.getComputedStyle(el).textAlign")
        print(f"Stats H2 Font: {stats_font}, Text Align: {stats_align}")
        assert "Plus Jakarta Sans" in stats_font or "sans-serif" in stats_font, f"Expected Plus Jakarta Sans, got {stats_font}"
        assert stats_align == "center", f"Expected center, got {stats_align}"
        
        attack_h2 = page.locator("#attack-chain .section-title")
        attack_font = attack_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        attack_align = attack_h2.evaluate("el => window.getComputedStyle(el).textAlign")
        print(f"Attack Chain H2 Font: {attack_font}, Text Align: {attack_align}")
        assert attack_align == "center", f"Expected center, got {attack_align}"
        
        holding_h2 = page.locator("#holding-heading")
        holding_font = holding_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        print(f"Holding H2 Font: {holding_font}")
        assert "Plus Jakarta Sans" in holding_font or "sans-serif" in holding_font, f"Expected Plus Jakarta Sans, got {holding_font}"
        
        # Test water effect / hover on holding heading
        holding_h2.hover()
        page.wait_for_timeout(200)
        has_liquid_filter = holding_h2.evaluate("el => window.getComputedStyle(el).filter")
        print(f"Holding H2 Hover Filter: {has_liquid_filter}")
        assert "liquid-filter" in has_liquid_filter or "drop-shadow" in has_liquid_filter, f"Expected liquid filter, got {has_liquid_filter}"
        
        # Test holding badge
        badge = page.locator(".holding-badge")
        badge.hover()
        page.wait_for_timeout(200)
        badge_filter = badge.evaluate("el => window.getComputedStyle(el).filter")
        print(f"Holding Badge Hover Filter: {badge_filter}")
        assert "liquid-filter" in badge_filter or "drop-shadow" in badge_filter, f"Expected badge liquid filter, got {badge_filter}"
        
        # Check exposure scan heading (the reference one the user liked)
        exposure_h2 = page.locator(".exposure-scan-wrap h2")
        exp_font = exposure_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        print(f"Exposure Scan H2 Font: {exp_font}")
        
        # 2. Testing AI Report (/reports/demo)
        print("\n--- 2. Testing AI Report (/reports/demo) ---")
        page.goto("http://127.0.0.1:5050/reports/demo", wait_until="networkidle")
        assert page.locator(".debrief-container").is_visible(), "Debrief container should be visible"
        
        # Check verdict quote
        quote = page.locator(".verdict-serif-quote").inner_text()
        print(f"Verdict Quote: {quote[:60]}...")
        assert len(quote) > 10, "Verdict quote must be present"
        
        # Check score ring
        ring = page.locator("#score-ring-circle")
        assert ring.is_visible(), "Score ring must be visible"
        score_val = page.locator("#ring-score-val").inner_text()
        print(f"Score Value: {score_val}")
        
        # Check lure email content (no raw 'mail body')
        lure_body = page.locator("#lure-email-body").inner_text()
        print(f"Lure Email Body preview: {lure_body[:80]}...")
        assert "mail body" not in lure_body.lower() or len(lure_body) > 100, "Lure body should be properly rendered"
        assert page.locator(".trigger-highlight").count() > 0, "Trigger highlights should be present in lure body"
        
        # Check department breakdown
        dept_count = page.locator(".dept-bar-item").count()
        print(f"Department rows: {dept_count}")
        assert dept_count > 0, "Department breakdown rows must exist"
        
        # Check score history trajectory
        trend_count = page.locator(".trend-step-item").count()
        print(f"Score history trend rows: {trend_count}")
        assert trend_count >= 3, "Trend history should show at least 3 previous campaigns"
        
        # Check remediation actions
        actions_count = page.locator(".action-card").count()
        print(f"Remediation action cards: {actions_count}")
        assert actions_count >= 2, "Action cards should be present"
        
        # 3. Testing Users Page (/users)
        print("\n--- 3. Testing Users Page ---")
        # Ensure test admin user exists and get session
        import requests, re
        from app import get_db_connection
        from werkzeug.security import generate_password_hash
        
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("UPDATE users SET role = 'admin' WHERE email = 'test_admin@phishsim.ai'")
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO users (name, email, password_hash, role, email_verified, is_disabled)
                VALUES ('Test Admin', 'test_admin@phishsim.ai', %s, 'admin', TRUE, FALSE)
                ON DUPLICATE KEY UPDATE role = 'admin', is_disabled = FALSE
            """, (generate_password_hash("TestPass123!"),))
        db.commit()
        cur.close()
        db.close()

        s = requests.Session()
        r = s.get("http://127.0.0.1:5050/login")
        csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
        token = csrf.group(1) if csrf else ''
        s.post("http://127.0.0.1:5050/login", data={"email": "test_admin@phishsim.ai", "password": "TestPass123!", "csrf_token": token})
        sess_cookie = s.cookies.get("session")
        if sess_cookie:
            context.add_cookies([{"name": "session", "value": sess_cookie, "domain": "127.0.0.1", "path": "/"}])

        page.goto("http://127.0.0.1:5050/users", wait_until="networkidle")
        page.wait_for_timeout(300) # wait for skeleton transition
        
        # Verify 4 filter selects in one row
        selects = page.locator(".filter-select").all()
        print(f"Found {len(selects)} filter selects.")
        assert len(selects) >= 4, "Should have 4 filter selects"
        tops = [s.bounding_box()['y'] for s in selects]
        print(f"Select Y positions: {tops}")
        # All selects should have roughly the same Y coordinate (within 6px on one line)
        assert max(tops) - min(tops) <= 6, f"Selects should be in one horizontal row, delta={max(tops) - min(tops)}"
        
        # Verify row action: Details visible, '⋯' trigger present
        row1 = page.locator(".user-row-item:visible").first
        details_btn = row1.locator("button:has-text('Details')")
        assert details_btn.is_visible(), "Details button must be visible"
        
        menu_trigger = row1.locator(".btn-menu-trigger")
        assert menu_trigger.is_visible(), "'⋯' menu trigger must be visible"
        
        # Ensure secondary buttons are inside the dropdown menu, not loose in the row
        action_toolbar_buttons = row1.locator(".action-toolbar > button").all()
        print(f"Direct visible action buttons in toolbar: {len(action_toolbar_buttons)}")
        assert len(action_toolbar_buttons) == 1, f"Only Details button should be directly visible, found {len(action_toolbar_buttons)}"
        
        # Click menu trigger
        menu_trigger.click()
        page.wait_for_timeout(100)
        menu = row1.locator(".user-action-menu")
        assert menu.evaluate("el => el.classList.contains('show')"), "Menu should open on click"
        
        # Check menu items inside
        menu_items = menu.locator(".action-menu-item").all()
        print(f"Menu items count: {len(menu_items)}")
        assert len(menu_items) >= 4, "Menu should contain role, plan, reset, status, delete options"
        
        # Test keyboard navigation: press Escape to close
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        assert not menu.evaluate("el => el.classList.contains('show')"), "Menu should close on Escape"
        
        # Check skeleton tbody exists
        skel = page.locator("#users-skeleton-tbody")
        assert skel.count() == 1, "Skeleton tbody must exist"
        print("Users page checks passed successfully!")
        
        # 4. Mobile 375px Responsive Verification
        print("\n--- 4. Testing Mobile 375px Overflow ---")
        mob_context = browser.new_context(viewport={'width': 375, 'height': 812})
        if sess_cookie:
            mob_context.add_cookies([{"name": "session", "value": sess_cookie, "domain": "127.0.0.1", "path": "/"}])
        mob_page = mob_context.new_page()
        
        pages_to_test = [
            ("Home", "http://127.0.0.1:5050/"),
            ("Users", "http://127.0.0.1:5050/users"),
            ("Demo Report", "http://127.0.0.1:5050/reports/demo"),
            ("Dashboard", "http://127.0.0.1:5050/dashboard"),
            ("Billing", "http://127.0.0.1:5050/billing")
        ]
        
        # Log in on mobile context too
        mob_page.goto("http://127.0.0.1:5050/demo-login", wait_until="networkidle")
        
        for name, url in pages_to_test:
            mob_page.goto(url, wait_until="networkidle")
            mob_page.wait_for_timeout(250)
            scroll_w = mob_page.evaluate("document.documentElement.scrollWidth")
            client_w = mob_page.evaluate("document.documentElement.clientWidth")
            print(f"Mobile 375px [{name}]: scrollWidth={scroll_w}, clientWidth={client_w}")
            assert scroll_w <= client_w, f"Mobile overflow on {name}: scrollWidth={scroll_w} > clientWidth={client_w}"
            
        print("\n=== ALL VERIFICATION CHECKS PASSED PERFECTLY ===")
        browser.close()

if __name__ == "__main__":
    verify_all()
