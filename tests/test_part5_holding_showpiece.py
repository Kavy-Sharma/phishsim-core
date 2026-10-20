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
        print(f"Warning: Could not fetch axe-core: {e}")
        return None


def safe_screenshot(p, path):
    try:
        p.screenshot(path=path, timeout=5000, animations="disabled")
    except Exception:
        try:
            p.locator("body").screenshot(path=path, timeout=5000, animations="disabled")
        except Exception as e:
            print(f"Warning: safe_screenshot failed for {path}: {e}")


def test_part5_holding_showpiece_suite():
    axe_source = get_axe_script()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--disable-remote-fonts"])

        # ══════════════════════════════════════════════════════════════
        # 1. VERIFY OLD TILES & ADVISOR GONE, OTHER SECTIONS STILL RENDER
        # ══════════════════════════════════════════════════════════════
        print("\n--- 1. Verifying Clean DOM & Surrounding Sections ---")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; }")

        # Check old tiles and old headers are gone
        old_grid = page.locator(".suite-grid")
        assert old_grid.count() == 0, "Old .suite-grid should be completely gone"
        old_cards = page.locator(".suite-card")
        assert old_cards.count() == 0, "Old .suite-card tiles should be completely gone"

        old_heading = page.locator("text='Advanced Defensive Infrastructure'")
        assert old_heading.count() == 0, "Old 'Advanced Defensive Infrastructure' heading should be gone"

        # Check that surrounding homepage sections still render properly
        sections_to_check = [
            "#hero",
            "#attack-chain",
            "#threat-sandbox",
            "#capabilities",
            "#global-threat-intel",
            "#solutions",
            "#threat-intel-suite",
            "#stats",
            "#pricing",
            "footer",
        ]
        for sec in sections_to_check:
            loc = page.locator(sec)
            assert loc.count() >= 1, f"Expected section {sec} to exist on home page"
            assert loc.first.is_visible(), f"Section {sec} should be visible"
        print("All homepage surrounding sections verified rendering cleanly!")

        # ══════════════════════════════════════════════════════════════
        # 2. DESKTOP INTERACTION: MOUSE, KEYBOARD, SCROLL & ZERO LAYOUT SHIFT
        # ══════════════════════════════════════════════════════════════
        print("\n--- 2. Testing Desktop Tabs, Keyboard, Scroll & Zero Layout Shift ---")
        section = page.locator("#threat-intel-suite")
        page.evaluate("() => document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' })")
        page.wait_for_timeout(300)
        page.evaluate("() => document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' })")
        page.wait_for_timeout(200)

        tab_email = page.locator("#holding-tab-email")
        tab_link = page.locator("#holding-tab-link")
        tab_pass = page.locator("#holding-tab-password")
        tab_domain = page.locator("#holding-tab-domain")

        panel_email = page.locator("#holding-panel-email")
        panel_link = page.locator("#holding-panel-link")
        panel_pass = page.locator("#holding-panel-password")
        panel_domain = page.locator("#holding-panel-domain")

        viewport_box = page.locator("#holding-stage-viewport")

        # Initial state should be email
        assert tab_email.get_attribute("aria-selected") == "true", "Email tab should be active by default"
        assert panel_email.is_visible(), "Email panel should be visible by default"

        # Record initial viewport dimensions
        initial_box = viewport_box.bounding_box()
        assert initial_box["height"] >= 380, f"Stage viewport height too small: {initial_box['height']}"

        # A. Mouse Click -> Link
        tab_link.click()
        page.wait_for_timeout(200)
        assert tab_link.get_attribute("aria-selected") == "true", "Link tab should be selected after click"
        assert panel_link.is_visible(), "Link panel should be visible"
        box_link = viewport_box.bounding_box()
        assert abs(box_link["height"] - initial_box["height"]) < 1.0, "Zero layout shift check failed on Link panel"

        # B. Mouse Click -> Password
        tab_pass.click()
        page.wait_for_timeout(200)
        assert tab_pass.get_attribute("aria-selected") == "true", "Password tab should be selected after click"
        assert panel_pass.is_visible(), "Password panel should be visible"
        box_pass = viewport_box.bounding_box()
        assert abs(box_pass["height"] - initial_box["height"]) < 1.0, "Zero layout shift check failed on Password panel"

        # C. Mouse Click -> Company Domain
        tab_domain.click()
        page.wait_for_timeout(200)
        assert tab_domain.get_attribute("aria-selected") == "true", "Domain tab should be selected after click"
        assert panel_domain.is_visible(), "Domain panel should be visible"
        box_domain = viewport_box.bounding_box()
        assert abs(box_domain["height"] - initial_box["height"]) < 1.0, "Zero layout shift check failed on Domain panel"

        # D. Keyboard Navigation (ArrowUp, ArrowDown, Home, End)
        tab_domain.focus()
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(150)
        assert tab_pass.get_attribute("aria-selected") == "true", "ArrowUp should navigate from Domain to Password"

        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(150)
        assert tab_link.get_attribute("aria-selected") == "true", "ArrowUp should navigate from Password to Link"

        page.keyboard.press("Home")
        page.wait_for_timeout(150)
        assert tab_email.get_attribute("aria-selected") == "true", "Home key should jump to first tab (Email)"

        page.keyboard.press("End")
        page.wait_for_timeout(150)
        assert tab_domain.get_attribute("aria-selected") == "true", "End key should jump to last tab (Domain)"

        page.keyboard.press("ArrowDown")  # wraps to Email
        page.wait_for_timeout(150)
        assert tab_email.get_attribute("aria-selected") == "true", "ArrowDown on last tab should wrap to first tab"

        # E. Verify Compact Height (No Unnecessary Gap Below Section)
        print("Verifying compact section height and no unnecessary gap below section...")
        gap_measurements = page.evaluate("""() => {
            const sec = document.getElementById('threat-intel-suite');
            const stats = document.getElementById('stats');
            const cta = document.getElementById('holding-domain-cta');
            const rSec = sec.getBoundingClientRect();
            const rCta = cta.getBoundingClientRect();
            const rStats = stats.getBoundingClientRect();
            return {
                sec_height: rSec.height,
                dist_cta_to_stats: rStats.top - rCta.bottom
            };
        }""")
        print(f"Measured: sec_height={gap_measurements['sec_height']}, dist_cta_to_stats={gap_measurements['dist_cta_to_stats']}")
        assert gap_measurements['sec_height'] < 1000, f"Section height too tall ({gap_measurements['sec_height']}px), expected compact natural height < 1000px"
        assert gap_measurements['dist_cta_to_stats'] < 160, f"Unnecessary gap below section detected ({gap_measurements['dist_cta_to_stats']}px), expected < 160px"
        print("Verified: Section has clean, compact natural height with zero unnecessary gap!")

        # ══════════════════════════════════════════════════════════════
        # 3. DOMAIN INPUT FORM CLIENT-SIDE VALIDATION & NAVIGATION
        # ══════════════════════════════════════════════════════════════
        print("\n--- 3. Testing Domain Input Form Client-side Validation ---")
        domain_input = page.locator("#holding-domain-input")
        domain_submit = page.locator("#holding-domain-submit")
        domain_error = page.locator("#holding-domain-error")

        # Empty submit: rejects
        domain_input.fill("")
        domain_submit.click()
        page.wait_for_timeout(150)
        assert domain_error.is_visible(), "Error message should show for empty domain input"
        assert "enter a company domain" in domain_error.text_content().lower()
        assert page.url.endswith("/"), "Should not navigate on empty domain"

        # Invalid domain format: rejects
        domain_input.fill("invalid-domain-no-tld")
        domain_submit.click()
        page.wait_for_timeout(150)
        assert domain_error.is_visible(), "Error message should show for invalid domain format"
        assert "invalid domain" in domain_error.text_content().lower()
        assert page.url.endswith("/"), "Should not navigate on invalid domain format"

        # Valid input with leading protocol and path: cleans and navigates to /exposure-report?domain=...
        domain_input.fill("https://www.cyber-test.org/login")
        # Listen for navigation
        with page.expect_navigation():
            domain_submit.click()
        assert "/exposure-report?domain=cyber-test.org" in page.url, f"Expected clean navigation, got: {page.url}"
        print(f"Domain form successfully cleaned input and navigated to: {page.url}")

        page.close()

        # ══════════════════════════════════════════════════════════════
        # 4. CAPTURE VISUAL SCREENSHOTS (1440, 1024, 390 IN DARK & LIGHT)
        # ══════════════════════════════════════════════════════════════
        print("\n--- 4. Capturing Multi-Breakpoint & Theme Screenshots ---")

        # A. Desktop 1440px Dark Theme
        p_dark = browser.new_page(viewport={"width": 1440, "height": 900})
        p_dark.goto(BASE_URL, wait_until="domcontentloaded")
        p_dark.wait_for_timeout(400)
        p_dark.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' }); }")
        p_dark.wait_for_timeout(300)

        # 1440 Dark: Default Email
        shot_1440_dark_email = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_dark_email.png")
        safe_screenshot(p_dark.locator("#threat-intel-suite"), shot_1440_dark_email)
        print(f"Captured: {shot_1440_dark_email}")

        # 1440 Dark: Link
        p_dark.locator("#holding-tab-link").click()
        p_dark.wait_for_timeout(400)
        shot_1440_dark_link = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_dark_link.png")
        safe_screenshot(p_dark.locator("#threat-intel-suite"), shot_1440_dark_link)

        # 1440 Dark: Password
        p_dark.locator("#holding-tab-password").click()
        p_dark.wait_for_timeout(400)
        shot_1440_dark_pass = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_dark_password.png")
        safe_screenshot(p_dark.locator("#threat-intel-suite"), shot_1440_dark_pass)

        # 1440 Dark: Domain Finale
        p_dark.locator("#holding-tab-domain").click()
        p_dark.wait_for_timeout(600)
        shot_1440_dark_domain = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_dark_domain.png")
        safe_screenshot(p_dark.locator("#threat-intel-suite"), shot_1440_dark_domain)
        print(f"Captured: {shot_1440_dark_domain}")

        # Accessibility Check (Dark)
        if axe_source:
            p_dark.evaluate(axe_source)
            res = p_dark.evaluate("""() => {
                return new Promise(resolve => {
                    axe.run(document.getElementById('threat-intel-suite'), {
                        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] }
                    }, (err, results) => {
                        resolve((results.violations || []).filter(v => v.impact === 'critical' || v.impact === 'serious'));
                    });
                });
            }""")
            print(f"Axe-core serious/critical violations on showpiece (dark): {len(res)}")
            assert len(res) == 0, f"Found axe violations: {res}"

        p_dark.close()

        # B. Desktop 1440px Light Theme
        p_light = browser.new_page(viewport={"width": 1440, "height": 900})
        p_light.goto(BASE_URL, wait_until="domcontentloaded")
        p_light.evaluate("""() => {
            document.documentElement.style.scrollBehavior = 'auto';
            document.documentElement.setAttribute('data-theme', 'light');
            document.body.classList.add('light-theme');
            localStorage.setItem('phishsim-theme', 'light');
            document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' });
        }""")
        p_light.wait_for_timeout(300)

        shot_1440_light_email = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_light_email.png")
        safe_screenshot(p_light.locator("#threat-intel-suite"), shot_1440_light_email)
        print(f"Captured: {shot_1440_light_email}")

        p_light.locator("#holding-tab-domain").click()
        p_light.wait_for_timeout(500)
        shot_1440_light_domain = os.path.join(ARTIFACTS_DIR, "part5_desktop_1440_light_domain.png")
        safe_screenshot(p_light.locator("#threat-intel-suite"), shot_1440_light_domain)
        print(f"Captured: {shot_1440_light_domain}")

        if axe_source:
            p_light.evaluate(axe_source)
            res = p_light.evaluate("""() => {
                return new Promise(resolve => {
                    axe.run(document.getElementById('threat-intel-suite'), {
                        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] }
                    }, (err, results) => {
                        resolve((results.violations || []).filter(v => v.impact === 'critical' || v.impact === 'serious'));
                    });
                });
            }""")
            print(f"Axe-core serious/critical violations on showpiece (light): {len(res)}")
            assert len(res) == 0, f"Found light axe violations: {res}"

        p_light.close()

        # C. Tablet 1024px (Dark & Light)
        p_tab = browser.new_page(viewport={"width": 1024, "height": 768})
        p_tab.goto(BASE_URL, wait_until="domcontentloaded")
        p_tab.wait_for_timeout(400)
        p_tab.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' }); }")
        p_tab.wait_for_timeout(300)
        shot_1024_dark = os.path.join(ARTIFACTS_DIR, "part5_tablet_1024_dark.png")
        safe_screenshot(p_tab.locator("#threat-intel-suite"), shot_1024_dark)
        print(f"Captured: {shot_1024_dark}")
        p_tab.close()

        # D. Mobile 390px (Dark & Light)
        p_mob = browser.new_page(viewport={"width": 390, "height": 844})
        p_mob.goto(BASE_URL, wait_until="domcontentloaded")
        p_mob.wait_for_timeout(400)
        p_mob.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' }); }")
        p_mob.wait_for_timeout(300)
        shot_390_dark = os.path.join(ARTIFACTS_DIR, "part5_mobile_390_dark.png")
        safe_screenshot(p_mob.locator("#threat-intel-suite"), shot_390_dark)
        print(f"Captured: {shot_390_dark}")

        # Switch tab on mobile
        p_mob.locator("#holding-tab-domain").click()
        p_mob.wait_for_timeout(300)
        assert p_mob.locator("#holding-panel-domain").is_visible(), "Domain panel should show on mobile click"

        # Mobile Light
        p_mob.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'light');
            document.body.classList.add('light-theme');
            localStorage.setItem('phishsim-theme', 'light');
        }""")
        p_mob.wait_for_timeout(300)
        shot_390_light = os.path.join(ARTIFACTS_DIR, "part5_mobile_390_light.png")
        safe_screenshot(p_mob.locator("#threat-intel-suite"), shot_390_light)
        print(f"Captured: {shot_390_light}")
        p_mob.close()

        # E. Reduced Motion Mode (forced prefers-reduced-motion: reduce)
        ctx_rm = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        p_rm = ctx_rm.new_page()
        p_rm.goto(BASE_URL, wait_until="domcontentloaded")
        p_rm.wait_for_timeout(400)
        p_rm.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; document.getElementById('threat-intel-suite').scrollIntoView({ block: 'start' }); }")
        p_rm.wait_for_timeout(300)

        p_rm.locator("#holding-tab-email").click()
        # With reduced motion, flagged urgency should be present immediately
        urgency_elem = p_rm.locator(".email-cue.is-flagged-urgency")
        assert urgency_elem.count() >= 1, "Underline cues should be present immediately with reduced motion"

        shot_rm = os.path.join(ARTIFACTS_DIR, "part5_reduced_motion_1440.png")
        safe_screenshot(p_rm.locator("#threat-intel-suite"), shot_rm)
        print(f"Captured: {shot_rm}")
        ctx_rm.close()

        browser.close()
        print("\nAll Part 5 Test Suite assertions and screenshots completed successfully!")


if __name__ == "__main__":
    test_part5_holding_showpiece_suite()
