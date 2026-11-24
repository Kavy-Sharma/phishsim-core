import os
import sys
from playwright.sync_api import sync_playwright

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("[*] Navigating to Home (1440px)...")
        page.goto("http://127.0.0.1:5050/", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # 1. Check fonts on section titles
        stats_h2 = page.locator("#stats .section-title")
        stats_font = stats_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        stats_weight = stats_h2.evaluate("el => window.getComputedStyle(el).fontWeight")
        stats_align = page.locator("#stats .stats-header").evaluate("el => window.getComputedStyle(el).textAlign")
        print(f"Stats H2 Font: {stats_font}, Weight: {stats_weight}, Header Align: {stats_align}")

        audit_h2 = page.locator("#join-beta h2")
        audit_font = audit_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        audit_weight = audit_h2.evaluate("el => window.getComputedStyle(el).fontWeight")
        print(f"Audit H2 Font: {audit_font}, Weight: {audit_weight}")

        # Check holding console badge and title
        holding_badge = page.locator(".holding-badge")
        holding_badge_font = holding_badge.evaluate("el => window.getComputedStyle(el).fontFamily")
        holding_h2 = page.locator("#holding-heading")
        holding_h2_font = holding_h2.evaluate("el => window.getComputedStyle(el).fontFamily")
        print(f"Holding Badge Font: {holding_badge_font}, Holding H2 Font: {holding_h2_font}")

        # Hover to trigger liquid effect
        holding_h2.hover()
        page.wait_for_timeout(300)
        has_liquid = holding_h2.evaluate("el => el.classList.contains('liquid-active') || el.classList.contains('liquid-text')")
        print(f"Holding H2 has liquid class/styling: {has_liquid}")

        # Capture screenshot of stats and holding section
        os.makedirs("artifacts_out", exist_ok=True)
        page.locator("#stats").screenshot(path="artifacts_out/home_stats_verified.png")
        page.locator("#threat-intel-suite").screenshot(path="artifacts_out/home_holding_verified.png")
        print("[+] Captured home stats and holding screenshots.")

        # 2. Check AI Report (/reports-demo)
        print("[*] Navigating to AI Campaign Report (/reports-demo)...")
        page.goto("http://127.0.0.1:5050/reports-demo", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # Check Score Ring
        score_val = page.locator("#ring-score-val").inner_text()
        print(f"Report Score: {score_val}/100")

        # Test Replay Button
        replay_btn = page.locator("#btn-replay-play")
        print("Clicking Replay button...")
        replay_btn.click()
        page.wait_for_timeout(1000)
        btn_text = page.locator("#replay-btn-text").inner_text()
        print(f"Replay Button State: {btn_text}")

        # Check Lure Email Content
        lure_body = page.locator("#lure-email-body").inner_html()
        print(f"Lure Body length: {len(lure_body)} chars, has marks: {'<mark' in lure_body}")

        # Toggle Triggers
        toggle_triggers = page.locator("#toggle-trigger-highlights")
        toggle_triggers.check()
        page.wait_for_timeout(300)
        force_active_marks = page.locator(".trigger-highlight.force-active").count()
        print(f"Trigger highlights revealed on toggle: {force_active_marks}")

        # Toggle Anonymise
        toggle_anon = page.locator("#toggle-anonymise")
        first_emp_name = page.locator(".emp-name").first.inner_text()
        print(f"Initial employee name: {first_emp_name}")
        toggle_anon.uncheck()
        first_emp_name_real = page.locator(".emp-name").first.inner_text()
        print(f"Unchecked anonymise: {first_emp_name_real}")

        # Click an enabled Remediation Action if available
        enabled_btn = page.locator(".action-btn-exec:not(:disabled)").first
        if enabled_btn.count() > 0:
            enabled_btn.click()
            page.wait_for_timeout(800)
            completed_count = page.locator(".action-done").count()
            print(f"Completed remediation actions after click: {completed_count}")
        else:
            print("All actions already completed or in final state.")

        # Screenshot the full report
        page.screenshot(path="artifacts_out/ai_report_showcase_verified.png", full_page=True)
        print("[+] Captured full AI report screenshot: artifacts_out/ai_report_showcase_verified.png")

        print(f"Total console errors logged: {len(console_errors)}")
        if console_errors:
            print("Console Errors:", console_errors)

        browser.close()

if __name__ == "__main__":
    verify()
