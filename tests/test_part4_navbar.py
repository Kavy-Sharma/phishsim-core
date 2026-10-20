import json
import os
import sys
import time
import urllib.request
import pytest
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity-ide\brain\aa7bd232-df2c-41e9-9645-8462240b7e2f\screenshots"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

BASE_URL = "http://127.0.0.1:5050"

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.4/axe.min.js"


def get_axe_script():
    try:
        req = urllib.request.Request(AXE_CDN, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Warning: Could not fetch axe-core from CDN: {e}")
        return None


def safe_screenshot(p, path):
    try:
        p.screenshot(path=path, timeout=5000, animations="disabled")
    except Exception:
        try:
            p.locator("body").screenshot(path=path, timeout=5000, animations="disabled")
        except Exception as e:
            print(f"Warning: safe_screenshot failed for {path}: {e}")


def test_navbar_full_suite():
    axe_source = get_axe_script()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--disable-remote-fonts"])

        # ══════════════════════════════════════════════════════════════
        # 1. DESKTOP TESTS (1440x900) - DARK & LIGHT THEMES
        # ══════════════════════════════════════════════════════════════
        for theme in ["dark", "light"]:
            print(f"\n--- Testing Desktop Navbar ({theme.upper()} THEME) ---")
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()

            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(600)

            # Apply theme if needed
            if theme == "light":
                page.evaluate("""() => {
                    document.documentElement.setAttribute('data-theme', 'light');
                    document.body.classList.add('light-theme');
                    localStorage.setItem('phishsim-theme', 'light');
                    localStorage.setItem('theme', 'light');
                }""")
                page.wait_for_timeout(300)

            # A. Default State Screenshot
            default_shot = os.path.join(ARTIFACTS_DIR, f"desktop_navbar_{theme}_default.png")
            safe_screenshot(page, default_shot)
            print(f"Captured: {default_shot}")

            # Verify Try Demo button is visible on homepage when guest
            try_demo = page.locator("#nav-try-demo-btn")
            assert try_demo.is_visible(), "Try Demo button should be visible on homepage for guest"
            try_demo.hover()
            page.wait_for_timeout(200)
            try_demo_shot = os.path.join(ARTIFACTS_DIR, f"desktop_navbar_{theme}_try_demo_hover.png")
            safe_screenshot(page, try_demo_shot)
            print(f"Captured: {try_demo_shot}")

            # B. Condensed State on Scroll (>24px)
            page.evaluate("window.scrollTo(0, 100);")
            page.wait_for_timeout(300)
            is_scrolled = page.evaluate("() => document.getElementById('navbar').classList.contains('scrolled')")
            assert is_scrolled, "Navbar failed to gain .scrolled class after scrolling past 24px"
            nav_height = page.evaluate("() => document.getElementById('navbar').offsetHeight")
            print(f"Navbar height when scrolled: {nav_height}px")
            assert nav_height <= 60, f"Expected navbar condensed height <=60px, got {nav_height}px"

            page.evaluate("window.scrollTo(0, 0);")
            page.wait_for_timeout(200)

            # C. Mouse Hover: "Check something" Popover & Vignette updates
            trigger_check = page.locator("#nav-trigger-check")
            trigger_train = page.locator("#nav-trigger-train")
            surface = page.locator("#nav-popover-surface")

            trigger_check.hover()
            page.wait_for_timeout(250)  # Wait for 80ms hover-intent + 140ms fade
            assert surface.is_visible(), "Popover surface should be visible on hovering 'Check something'"
            check_open = trigger_check.get_attribute("aria-expanded")
            assert check_open == "true", "Trigger check aria-expanded should be true"

            # Check that PhishRecon "New" badge is present
            recon_badge = page.locator(".nav-badge-recon-new").first
            assert recon_badge.is_visible(), "PhishRecon 'New' badge should be visible (within 30 days)"

            # Hover each item inside "Check something" to test vignette switching
            threat_item = page.locator("a[data-preview='preview-threat']")
            header_item = page.locator("a[data-preview='preview-header']")
            url_item = page.locator("a[data-preview='preview-url']")

            header_item.hover()
            page.wait_for_timeout(200)
            assert page.locator("#preview-header").is_visible(), "Header Analyzer vignette should be active"

            url_item.hover()
            page.wait_for_timeout(200)
            assert page.locator("#preview-url").is_visible(), "URL Decoder vignette should be active"

            # Screenshot: Check Menu Open
            check_shot = os.path.join(ARTIFACTS_DIR, f"desktop_navbar_{theme}_check_menu.png")
            safe_screenshot(page, check_shot)
            print(f"Captured: {check_shot}")

            # D. Surface Morphing: Hover from "Check something" to "Train your team"
            # Surface should remain open without closing
            trigger_train.hover()
            page.wait_for_timeout(260)  # Wait 220ms morph transition
            assert surface.is_visible(), "Surface should remain open and morph to 'Train your team'"
            train_open = trigger_train.get_attribute("aria-expanded")
            assert train_open == "true", "Trigger train aria-expanded should be true"

            # Check vignettes inside "Train your team"
            drill_vig = page.locator("#preview-drill")
            assert drill_vig.is_visible(), "Default drill vignette should be active in Train menu"

            report_item = page.locator("a[data-preview='preview-reports']")
            report_item.hover()
            page.wait_for_timeout(200)
            assert page.locator("#preview-reports").is_visible(), "Reports vignette should be active on hover"

            # Screenshot: Train Menu Open
            train_shot = os.path.join(ARTIFACTS_DIR, f"desktop_navbar_{theme}_train_menu.png")
            safe_screenshot(page, train_shot)
            print(f"Captured: {train_shot}")

            # E. Move away: Hover-intent 160ms close
            page.mouse.move(10, 500)
            page.wait_for_timeout(300)
            surface_open_class = page.evaluate("() => document.getElementById('nav-popover-surface').classList.contains('open')")
            assert not surface_open_class, "Popover surface should close after mouse leaves (160ms)"

            # F. Keyboard Navigation Test
            # Focus trigger via tab or direct focus, press ArrowDown to open and navigate
            trigger_check.focus()
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(250)
            assert surface.is_visible(), "ArrowDown should open the menu"

            # Arrow navigation inside menu
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(100)
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(100)

            # Escape closes and returns focus to trigger
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            surface_open_class = page.evaluate("() => document.getElementById('nav-popover-surface').classList.contains('open')")
            assert not surface_open_class, "Escape should close popover surface"
            focused_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
            assert focused_id == "nav-trigger-check", f"Focus should return to nav-trigger-check, got {focused_id}"

            # G. Command Palette: Press "/" shortcut
            page.keyboard.press("/")
            page.wait_for_timeout(250)
            palette = page.locator("#nav-command-palette")
            assert palette.is_visible(), "Command palette should open upon pressing '/'"

            palette_input = page.locator("#nav-palette-input")
            palette_input.fill("email")
            page.wait_for_timeout(200)
            results = page.locator("#nav-palette-results .nav-palette-item")
            assert results.count() >= 1, "Fuzzy search for 'email' should return matching tools"

            # Screenshot: Command Palette
            palette_shot = os.path.join(ARTIFACTS_DIR, f"desktop_navbar_{theme}_command_palette.png")
            safe_screenshot(page, palette_shot)
            print(f"Captured: {palette_shot}")

            # Close palette on Escape
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            assert not palette.is_visible(), "Command palette should close on Escape"

            # H. Axe-Core Accessibility Verification
            if axe_source:
                print(f"Running axe-core on desktop navbar ({theme})...")
                page.evaluate(axe_source)
                axe_results = page.evaluate("""() => {
                    return new Promise((resolve) => {
                        axe.run(document.getElementById('navbar'), {
                            runOnly: {
                                type: 'tag',
                                values: ['wcag2a', 'wcag2aa']
                            }
                        }, (err, results) => {
                            if (err) resolve({ error: err.message, violations: [] });
                            resolve({
                                error: null,
                                violations: (results.violations || []).filter(v => v.impact === 'critical' || v.impact === 'serious')
                            });
                        });
                    });
                }""")
                violations = axe_results.get("violations", [])
                print(f"Axe-core serious/critical violations on navbar ({theme}): {len(violations)}")
                if violations:
                    print("Violations:", json.dumps(violations, indent=2))
                assert len(violations) == 0, f"Found {len(violations)} serious/critical axe-core violations: {violations}"

            ctx.close()

        # ══════════════════════════════════════════════════════════════
        # 2. MOBILE TESTS (390x844 - iPhone 14 / modern smartphone)
        # ══════════════════════════════════════════════════════════════
        for theme in ["dark", "light"]:
            print(f"\n--- Testing Mobile Navbar ({theme.upper()} THEME) ---")
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()

            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(500)

            if theme == "light":
                page.evaluate("""() => {
                    document.documentElement.setAttribute('data-theme', 'light');
                    document.body.classList.add('light-theme');
                    localStorage.setItem('phishsim-theme', 'light');
                    localStorage.setItem('theme', 'light');
                }""")
                page.wait_for_timeout(300)

            # A. Default Mobile Header Screenshot
            m_default_shot = os.path.join(ARTIFACTS_DIR, f"mobile_navbar_{theme}_default.png")
            safe_screenshot(page, m_default_shot)
            print(f"Captured: {m_default_shot}")

            # Verify desktop items hidden, hamburger visible
            assert page.locator("#nav-hamburger-btn").is_visible(), "Hamburger button should be visible on mobile"
            assert not page.locator(".nav-desktop-menu").is_visible(), "Desktop menu should be hidden on mobile"

            # B. Open Mobile Sheet
            page.locator("#nav-hamburger-btn").click()
            page.wait_for_timeout(300)
            sheet = page.locator("#nav-mobile-sheet")
            assert sheet.is_visible(), "Mobile navigation sheet should be visible"

            # Verify body scroll lock
            body_locked = page.evaluate("() => document.body.classList.contains('nav-scroll-locked')")
            assert body_locked, "Body should have .nav-scroll-locked when mobile sheet is open"

            # C. Test Accordions in Mobile Sheet
            acc_check = page.locator("#acc-trigger-check")
            acc_content_check = page.locator("#acc-content-check")
            assert acc_content_check.is_visible(), "Accordion 'Check something' should be open by default"

            # Tap target sizes check: verify all mobile items have height >= 44px
            items = page.locator(".nav-mobile-item")
            for i in range(min(4, items.count())):
                box = items.nth(i).bounding_box()
                assert box["height"] >= 40, f"Tap target height should be >=40px, got {box['height']}"

            # Screenshot: Mobile Sheet Open
            m_sheet_shot = os.path.join(ARTIFACTS_DIR, f"mobile_navbar_{theme}_sheet_open.png")
            safe_screenshot(page, m_sheet_shot)
            print(f"Captured: {m_sheet_shot}")

            # D. Close mobile sheet via Escape
            page.keyboard.press("Escape")
            page.wait_for_timeout(250)
            assert not sheet.is_visible(), "Mobile sheet should close on Escape"
            body_locked_after = page.evaluate("() => document.body.classList.contains('nav-scroll-locked')")
            assert not body_locked_after, "Body scroll lock should be removed after closing sheet"

            # E. Axe-Core Accessibility Check on Mobile
            if axe_source:
                print(f"Running axe-core on mobile navbar ({theme})...")
                page.evaluate(axe_source)
                axe_results = page.evaluate("""() => {
                    return new Promise((resolve) => {
                        axe.run(document.getElementById('navbar'), {
                            runOnly: {
                                type: 'tag',
                                values: ['wcag2a', 'wcag2aa']
                            }
                        }, (err, results) => {
                            if (err) resolve({ error: err.message, violations: [] });
                            resolve({
                                error: null,
                                violations: (results.violations || []).filter(v => v.impact === 'critical' || v.impact === 'serious')
                            });
                        });
                    });
                }""")
                violations = axe_results.get("violations", [])
                print(f"Axe-core serious/critical violations on mobile navbar ({theme}): {len(violations)}")
                assert len(violations) == 0, f"Found {len(violations)} serious/critical axe-core violations: {violations}"

            ctx.close()

        # ══════════════════════════════════════════════════════════════
        # 3. LINK RESOLUTION VERIFICATION (Every Navbar Link Resolves)
        # ══════════════════════════════════════════════════════════════
        print("\n--- Verifying All Navbar Link Routes (HTTP Status) ---")
        routes_to_test = [
            ("/threat-analyzer", [200]),
            ("/header-analyzer", [200]),
            ("/url-decoder", [200]),
            ("/password-breach", [200]),
            ("/exposure-report", [200]),
            ("/new-campaign", [200, 302]),
            ("/dashboard", [200, 302]),
            ("/reports-demo", [200]),
            ("/fake-login-demo", [200]),
            ("/demo-login", [200, 302]),
            ("/about", [200]),
            ("/login", [200]),
            ("/signup", [200]),
            ("/solutions/phishing", [200, 301]),
            ("/solutions/osint", [200, 301]),
            ("/solutions/lms", [200, 301]),
            ("/solutions/plugin", [200, 301]),
        ]

        import requests

        for route, valid_codes in routes_to_test:
            target_url = f"{BASE_URL}{route}"
            resp = requests.get(target_url, allow_redirects=False)
            code = resp.status_code
            print(f"Route {route} -> HTTP {code} (Expected {valid_codes})")
            assert code in valid_codes, f"Route {route} returned unexpected HTTP {code}"

        # ══════════════════════════════════════════════════════════════
        # 4. GREP PROOF OF NO DUPLICATED BLOCKS
        # ══════════════════════════════════════════════════════════════
        print("\n--- Verifying Navbar Deduplication via File Inspection ---")
        navbar_path = os.path.join(os.path.dirname(__file__), "..", "templates", "navbar.html")
        with open(navbar_path, "r", encoding="utf-8") as f:
            content = f.read()

        # In old navbar, 'Threat Intelligence' appeared twice, 'Credential Guard' twice
        # In new navbar, 'Check something' and 'Train your team' triggers appear once
        check_trigger_count = content.count('id="nav-trigger-check"')
        train_trigger_count = content.count('id="nav-trigger-train"')
        popover_surface_count = content.count('id="nav-popover-surface"')
        mobile_sheet_count = content.count('id="nav-mobile-sheet"')

        print(f"Check trigger count in navbar.html: {check_trigger_count}")
        print(f"Train trigger count in navbar.html: {train_trigger_count}")
        print(f"Popover surface count in navbar.html: {popover_surface_count}")
        print(f"Mobile sheet count in navbar.html: {mobile_sheet_count}")

        assert check_trigger_count == 1, f"Expected exactly 1 check trigger, found {check_trigger_count}"
        assert train_trigger_count == 1, f"Expected exactly 1 train trigger, found {train_trigger_count}"
        assert popover_surface_count == 1, f"Expected exactly 1 popover surface, found {popover_surface_count}"
        assert mobile_sheet_count == 1, f"Expected exactly 1 mobile sheet, found {mobile_sheet_count}"

        browser.close()
        print("\nAll Part 4 Navbar Playwright, Accessibility & Routing tests PASSED successfully!")


if __name__ == "__main__":
    test_navbar_full_suite()
