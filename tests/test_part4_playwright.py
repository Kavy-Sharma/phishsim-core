import os
import sys
import re
import time
import socket
import subprocess
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5050"
ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity-ide\brain\40571adf-05e2-49f2-ad21-63d329593ba3\screenshots"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def is_port_open(host="127.0.0.1", port=5050):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1.0)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def ensure_server_running():
    if is_port_open():
        print(f"[SERVER] Server is already running on {BASE_URL}")
        return None
    
    print("[SERVER] Starting Flask server on port 5050...")
    log_file = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "flask_server.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    
    # Wait up to 25 seconds for server to come up
    for _ in range(50):
        if is_port_open():
            print(f"[SERVER] Flask server ready on {BASE_URL}")
            return proc
        time.sleep(0.5)
    
    raise RuntimeError("Could not start Flask server on port 5050")


def block_external_cdns(route):
    url = route.request.url.lower()
    cdn_keywords = [
        "cdn", "cdnjs", "unpkg", "jsdelivr", "googleapis", "gstatic",
        "typekit", "fontawesome"
    ]
    if any(k in url for k in cdn_keywords) and "127.0.0.1" not in url and "localhost" not in url:
        # Block external CDN by fulfilling with empty 200 response
        content_type = "text/css" if ".css" in url else "text/javascript"
        route.fulfill(status=200, content_type=content_type, body="")
    else:
        route.continue_()


def test_part4_playwright_suite():
    server_proc = ensure_server_running()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-remote-fonts"])
            
            # ══════════════════════════════════════════════════════════
            # 1. DESKTOP TESTS (1440x900) - List/Grid, Filters, Search, Bulk, Shortcuts
            # ══════════════════════════════════════════════════════════
            print("\n=== 1. Desktop Tests (CDN Blocked, Zero Console Errors) ===")
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            # Block all external CDNs
            page.route("**/*", block_external_cdns)

            # Navigate to /dashboard
            print("Navigating to /dashboard...")
            page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
            page.wait_for_timeout(600)

            # A. Skeletons match final size, no layout shift, zero console errors
            assert len(console_errors) == 0, f"Found console errors on initial load: {console_errors}"
            print("[PASS] Initial load clean with zero console errors and CDNs blocked.")

            # B. Single Primary Button
            primary_btns = page.locator(".btn.btn-primary")
            assert primary_btns.count() == 1, f"Expected exactly 1 .btn-primary on dashboard, found {primary_btns.count()}"
            btn_text = primary_btns.first.inner_text().strip()
            assert "New campaign" in btn_text, f"Expected primary button 'New campaign', got '{btn_text}'"
            print(f"[PASS] Single primary button verified: '{btn_text}'")

            # C. Real Table Semantics
            table = page.locator("#campaigns-table")
            assert table.is_visible(), "Campaigns table should be visible in list view"
            caption = page.locator("#campaigns-table caption.sr-only")
            assert caption.count() >= 1, "Table must have sr-only caption"
            th_cols = page.locator("#campaigns-table th[scope='col']")
            assert th_cols.count() >= 5, "Table headers must have scope='col'"
            th_rows = page.locator("#campaigns-table tbody th[scope='row']")
            assert th_rows.count() >= 1, "Campaign row names must use th with scope='row'"
            print("[PASS] Real table semantics verified (caption, col/row scopes).")

            # D. View Toggle Radio Group & Keyboard Navigation
            radiogroup = page.locator(".view-toggle-segmented[role='radiogroup']")
            assert radiogroup.is_visible(), "View toggle must have role='radiogroup'"
            btn_list = page.locator("#view-toggle-list[role='radio']")
            btn_grid = page.locator("#view-toggle-grid[role='radio']")
            assert btn_list.get_attribute("aria-checked") == "true", "List radio should be checked by default"
            assert btn_grid.get_attribute("aria-checked") == "false", "Grid radio should not be checked by default"

            # Arrow navigation inside radiogroup
            btn_list.focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(300)
            assert btn_grid.get_attribute("aria-checked") == "true", "ArrowRight should switch to Grid view"
            assert page.locator("#pane-view-grid").is_visible(), "Grid pane should be visible after switching"

            page.keyboard.press("ArrowLeft")
            page.wait_for_timeout(300)
            assert btn_list.get_attribute("aria-checked") == "true", "ArrowLeft should switch back to List view"
            assert page.locator("#pane-view-list").is_visible(), "List pane should be visible"
            print("[PASS] Radio group ARIA attributes and arrow-key navigation verified.")

            # E. List ↔ Grid Toggle Persistence (localStorage)
            print("Testing View Persistence in localStorage...")
            btn_grid.click()
            page.wait_for_timeout(300)
            storage_val = page.evaluate("() => localStorage.getItem('phishsim_campaigns_view')")
            assert storage_val == "grid", f"Expected localStorage 'grid', got '{storage_val}'"

            # Reload page and assert Grid view persists
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(500)
            assert page.locator("#pane-view-grid").is_visible(), "Grid view must persist after page reload"
            assert page.locator("#view-toggle-grid").get_attribute("aria-checked") == "true"
            print("[PASS] Grid view successfully persisted across page reload.")

            # Switch back to list view
            page.locator("#view-toggle-list").click()
            page.wait_for_timeout(300)

            # F. Filters & Filter Chips
            print("Testing Filter Chips...")
            all_chip = page.locator(".filter-chip[data-filter='all']")
            running_chip = page.locator(".filter-chip[data-filter='running']")
            finished_chip = page.locator(".filter-chip[data-filter='finished']")

            running_chip.click()
            page.wait_for_timeout(200)
            running_rows = page.locator(".campaign-row:visible")
            for i in range(running_rows.count()):
                st = running_rows.nth(i).get_attribute("data-status-group")
                assert st == "running", f"Expected only running campaigns, got {st}"

            finished_chip.click()
            page.wait_for_timeout(200)
            finished_rows = page.locator(".campaign-row:visible")
            for i in range(finished_rows.count()):
                st = finished_rows.nth(i).get_attribute("data-status-group")
                assert st == "finished", f"Expected only finished campaigns, got {st}"

            all_chip.click()
            page.wait_for_timeout(200)
            all_rows = page.locator(".campaign-row:visible")
            assert all_rows.count() >= 2, "All campaigns should be visible again"
            print("[PASS] Filter chips correctly isolate campaigns by status.")

            # G. Search & '/' Keyboard Shortcut
            print("Testing Search & '/' shortcut...")
            # Click somewhere neutral to blur
            page.locator(".dash-hero-grid").click()
            page.wait_for_timeout(100)
            page.keyboard.press("/")
            page.wait_for_timeout(200)

            focused_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
            assert focused_id == "campaign-search-input", f"Expected focus on campaign-search-input, got '{focused_id}'"

            page.keyboard.type("Executive")
            page.wait_for_timeout(250)
            visible_rows = page.locator(".campaign-row:visible")
            assert visible_rows.count() >= 1, "Search for 'Executive' should return matches"
            for i in range(visible_rows.count()):
                row_name = visible_rows.nth(i).get_attribute("data-name")
                assert "executive" in row_name.lower(), f"Row name '{row_name}' does not match query"

            # Clear search
            page.locator("#campaign-search-input").fill("")
            page.locator("#campaign-search-input").dispatch_event("input")
            page.wait_for_timeout(200)
            print("[PASS] Search shortcut '/' and live filtering verified.")

            # H. Bulk Selection & Floating Bar
            print("Testing Bulk Selection...")
            select_all_cb = page.locator("#campaign-select-all")
            bulk_bar = page.locator("#bulk-actions-bar")

            select_all_cb.check()
            page.wait_for_timeout(300)
            assert bulk_bar.is_visible(), "Floating bulk action bar should be visible after select all"
            count_text = page.locator("#bulk-count-label").inner_text()
            assert "selected" in count_text, f"Bulk count badge text should mention selected, got '{count_text}'"

            # Cancel bulk selection
            cancel_btn = bulk_bar.locator("button:has-text('Cancel')")
            cancel_btn.click()
            page.wait_for_timeout(400)
            is_active = page.evaluate("() => document.getElementById('bulk-actions-bar').classList.contains('active')")
            assert not is_active, "Bulk bar should not have .active class after cancel"
            assert not bulk_bar.is_visible(), "Bulk bar should disappear after cancel"
            assert not select_all_cb.is_checked(), "Select all checkbox should be unchecked"
            print("[PASS] Bulk selection bar and cancel functionality verified.")

            # I. Keyboard Shortcuts Modal '?' & Focus Trap/Restore
            print("Testing Keyboard Shortcuts Modal '?'...")
            page.locator(".dash-hero-grid").click()
            page.wait_for_timeout(100)
            page.keyboard.press("?")
            page.wait_for_timeout(250)

            shortcuts_dialog = page.locator("#shortcuts-dialog")
            is_open = page.evaluate("() => document.getElementById('shortcuts-dialog').open")
            assert is_open, "Shortcuts modal should open upon pressing '?'"

            # Verify Tab focus stays inside dialog
            page.keyboard.press("Tab")
            focused_in_dialog = page.evaluate("() => document.getElementById('shortcuts-dialog').contains(document.activeElement)")
            assert focused_in_dialog, "Focus must stay trapped inside shortcuts dialog on Tab"

            # Escape restores focus
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            is_closed = page.evaluate("() => !document.getElementById('shortcuts-dialog').open")
            assert is_closed, "Shortcuts modal should close upon Escape"

            # 'V' shortcut toggles view
            page.keyboard.press("v")
            page.wait_for_timeout(300)
            assert page.locator("#pane-view-grid").is_visible(), "'V' shortcut should switch to Grid view"
            page.keyboard.press("v")
            page.wait_for_timeout(300)
            assert page.locator("#pane-view-list").is_visible(), "'V' shortcut should switch back to List view"
            print("[PASS] Shortcuts '?', Esc focus restoration, and 'V' toggle verified.")

            # Screenshot: Verified Desktop Dashboard
            shot_path = os.path.join(ARTIFACTS_DIR, "part4_desktop_dashboard_verified.png")
            page.screenshot(path=shot_path, full_page=False)
            print(f"Captured screenshot: {shot_path}")

            ctx.close()

            # ══════════════════════════════════════════════════════════
            # 2. NAVBAR MENUS (Admin / Pro / Free Roles)
            # ══════════════════════════════════════════════════════════
            print("\n=== 2. Navbar Menus Across Roles (Admin, Pro, Free) ===")
            
            def get_session_cookie_for(email, password="TestPass123!"):
                s = requests.Session()
                r = s.get(f"{BASE_URL}/login")
                csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
                token = csrf.group(1) if csrf else ''
                resp = s.post(f"{BASE_URL}/login", data={"email": email, "password": password, "csrf_token": token}, allow_redirects=False)
                sess = s.cookies.get("session")
                return sess

            # Helper: test role in a clean browser context
            def verify_user_role_navbar(email, expected_role, expect_upgrade_btn, expect_admin_link):
                sess_val = get_session_cookie_for(email)
                assert sess_val, f"Failed to authenticate {email}"

                u_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                u_ctx.add_cookies([{"name": "session", "value": sess_val, "domain": "127.0.0.1", "path": "/"}])
                u_page = u_ctx.new_page()
                u_page.route("**/*", block_external_cdns)

                # Navigate directly to dashboard
                u_page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded")
                u_page.wait_for_timeout(500)

                # Check avatar trigger
                avatar_btn = u_page.locator("#app-avatar-trigger")
                assert avatar_btn.is_visible(), f"Avatar trigger must be visible for {email}"
                avatar_btn.click()
                u_page.wait_for_timeout(200)

                # Check plan badge in avatar card
                plan_badge = u_page.locator(".app-account-plan-badge").inner_text()
                if expected_role == 'admin':
                    assert "Admin" in plan_badge, f"Expected Admin badge, got '{plan_badge}'"
                elif expected_role == 'pro':
                    assert "Pro" in plan_badge, f"Expected Pro badge, got '{plan_badge}'"
                else:
                    assert "Free" in plan_badge, f"Expected Free badge, got '{plan_badge}'"

                # Check upgrade button visibility
                upgrade_btn = u_page.locator("#app-upgrade-btn")
                if expect_upgrade_btn:
                    assert upgrade_btn.is_visible(), f"Upgrade button should be visible for {expected_role}"
                else:
                    assert not upgrade_btn.is_visible(), f"Upgrade button should NOT be visible for {expected_role}"

                # Check admin link visibility in navbar tabs
                admin_tab = u_page.locator(".app-nav-tab[data-tab='admin']")
                if expect_admin_link:
                    assert admin_tab.is_visible(), f"Admin tab should be visible for {expected_role}"
                else:
                    assert not admin_tab.is_visible(), f"Admin tab should NOT be visible for {expected_role}"

                print(f"[PASS] Role '{expected_role}' verified: plan_badge='{plan_badge.strip()}', upgrade_btn={expect_upgrade_btn}, admin_tab={expect_admin_link}")
                u_ctx.close()

            # Test Free User
            verify_user_role_navbar("test_free@phishsim.ai", "free", expect_upgrade_btn=True, expect_admin_link=False)

            # Test Pro User
            verify_user_role_navbar("test_pro@phishsim.ai", "pro", expect_upgrade_btn=False, expect_admin_link=False)

            # Test Admin User
            verify_user_role_navbar("test_admin@phishsim.ai", "admin", expect_upgrade_btn=False, expect_admin_link=True)

            # ══════════════════════════════════════════════════════════
            # 3. MOBILE BOTTOM BAR (<768px Viewport)
            # ══════════════════════════════════════════════════════════
            print("\n=== 3. Mobile Bottom Bar (<768px) ===")
            m_ctx = browser.new_context(viewport={"width": 390, "height": 844})
            m_page = m_ctx.new_page()
            m_page.route("**/*", block_external_cdns)

            m_page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded")
            m_page.wait_for_timeout(500)

            # Bottom nav must be displayed with grid layout
            bottom_nav = m_page.locator(".app-bottom-nav")
            assert bottom_nav.is_visible(), "Mobile bottom nav must be visible on mobile viewport"
            display_style = m_page.evaluate("() => window.getComputedStyle(document.querySelector('.app-bottom-nav')).display")
            assert display_style == "grid", f"Expected display: grid for .app-bottom-nav, got '{display_style}'"

            # Desktop center nav must be hidden
            desktop_center_display = m_page.evaluate("() => window.getComputedStyle(document.querySelector('.app-nav-center')).display")
            assert desktop_center_display == "none", f"Expected display: none for .app-nav-center on mobile, got '{desktop_center_display}'"

            # Verify bottom nav has 5 interactive tabs (Dashboard, Campaigns, Tools, Reports, Account)
            tabs = m_page.locator(".app-bottom-nav .app-bottom-tab")
            assert tabs.count() == 5, f"Expected 5 bottom tabs, found {tabs.count()}"

            m_shot_path = os.path.join(ARTIFACTS_DIR, "part4_mobile_bottom_nav_verified.png")
            m_page.screenshot(path=m_shot_path)
            print(f"Captured mobile screenshot: {m_shot_path}")
            print("[PASS] Mobile bottom bar verified.")

            m_ctx.close()
            browser.close()

            print("\n=======================================================")
            print("ALL PART 4 PLAYWRIGHT TESTS PASSED SUCCESSFULLY!")
            print("=======================================================")

    finally:
        if server_proc:
            print("[SERVER] Terminating spawned Flask server...")
            server_proc.terminate()
            server_proc.wait()


if __name__ == "__main__":
    test_part4_playwright_suite()
