import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = r"C:\Users\user\.gemini\antigravity-ide\brain\4a12513e-979f-43a2-833d-a42f1dbd9591"


def run_browser_verification():
    print("Starting Playwright browser verification for PhishRecon Part 2...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)

        # ── 1. Desktop & Hostile Packet Injection Test ──────────────────
        print("\n--- TEST A: Hostile Packet Replay & XSS Proof ---")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        dialog_events = []
        page.on("dialog", lambda d: dialog_events.append(d.message))

        page.goto("http://127.0.0.1:5050/exposure-report?sample=default&debug=1", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # Inject hostile packet through dispatch
        hostile_packet = {
            "stage": "email_auth",
            "status": "ok",
            "spf": {
                "status": "open",
                "grade": "<script>window.__xss_spf=1</script>",
                "detail": "SPF <img src=x onerror=window.__xss_detail=1>",
                "raw": "v=spf1 <script>alert(1)</script> +all",
            },
            "dmarc": {
                "status": "missing",
                "grade": "<b onmouseover=alert(1)>Exposed</b>",
                "detail": "None",
                "raw": "javascript:alert(1)",
            },
        }

        page.evaluate("(packet) => { window.dispatch(packet); window.render(); }", hostile_packet)
        page.wait_for_timeout(500)

        # Verify nothing executed
        has_xss = page.evaluate("() => window.__xss_spf !== undefined || window.__xss_detail !== undefined")
        print(f"XSS payload executed: {has_xss}")
        assert not has_xss, "SECURITY FAILURE: XSS payload executed in browser!"
        assert len(dialog_events) == 0, f"Alert dialog triggered: {dialog_events}"

        # Verify no script or unescaped img tags exist in DOM
        injected_scripts = page.evaluate("() => document.querySelectorAll('script[src*=\"xss\"], img[onerror]').length")
        assert injected_scripts == 0, "Hostile elements were rendered as raw DOM nodes!"

        # ── 2. Six-Check Ledger & Structure Assertions ──────────────────
        print("\n--- TEST B: Six-Check Ledger Verification ---")
        ledger_count = page.evaluate("() => document.querySelectorAll('.pr-check-row').length")
        print(f"Ledger row count: {ledger_count} (expected 6)")
        assert ledger_count == 6, f"Expected exactly 6 ledger rows, got {ledger_count}!"

        check_ids = page.evaluate("() => Array.from(document.querySelectorAll('.pr-check-row')).map(r => r.getAttribute('data-check-id'))")
        print(f"Ledger check IDs: {check_ids}")
        assert "email_auth" in check_ids, "email_auth must be present in the ledger!"

        # ── 3. "Not Enough Data" Degradation Verification ──────────────
        print("\n--- TEST C: 'Not Enough Data' Degradation & Unassessed Display ---")
        offline_summary = {
            "stage": "summary",
            "success": True,
            "domain": "offline-target.example",
            "exposure_score": None,
            "posture": "Not enough data",
            "score_breakdown": {
                "lookalikes_points": 0,
                "email_auth_points": 0,
                "domain_age_points": 0,
                "ssl_points": 0,
                "subdomains_points": 0,
                "surface_points": 0,
            },
            "incomplete": ["domain age", "TLS", "email authentication", "look-alike domains", "subdomains", "public surface"],
            "path_used": "heuristic_only",
            "executive_verdict": "Could not complete enough checks to rate offline-target.example. Please try again."
        }

        page.evaluate("""(summary) => {
            if (window.abortInFlight) window.abortInFlight();
            window.resetState({
                domain: 'offline-target.example',
                phase: 'complete',
                summary: summary,
                checks: {
                    domain: { status: 'unavailable', data: null },
                    tls: { status: 'unavailable', data: null },
                    email_auth: { status: 'unavailable', data: null },
                    lookalikes: { status: 'unavailable', data: null },
                    subdomains: { status: 'unavailable', data: null },
                    surface: { status: 'unavailable', data: null }
                }
            });
            window.render();
        }""", offline_summary)
        page.wait_for_timeout(400)

        score_text = page.evaluate("() => document.getElementById('pr-score-numeral').textContent.trim()")
        posture_text = page.evaluate("() => document.getElementById('pr-posture-word').textContent.trim()")
        assert score_text == "—", f"Expected '—', got '{score_text}'"
        assert posture_text == "Not enough data", f"Expected 'Not enough data', got '{posture_text}'"

        unassessed_count = page.evaluate("() => document.querySelectorAll('.pr-check-points.is-unavailable').length")
        print(f"Unassessed check rows: {unassessed_count} (expected 6)")
        assert unassessed_count == 6, f"All 6 checks must degrade to unassessed! Got {unassessed_count}"

        # ── 4. Screenshots for All 5 Sample Variants in Both Themes ───────
        variants = ["default", "partial", "low", "critical", "no_mail"]
        print(f"\n--- TEST D: Capturing 5 Variants x 2 Themes (10 screenshots) ---")

        for var in variants:
            demo_domain = "acme-assets.example" if var == "no_mail" else "acme.example"

            # ── Dark Theme ──
            page.goto(f"http://127.0.0.1:5050/exposure-report?sample={var}&debug=1", wait_until="domcontentloaded")
            page.evaluate(f"() => {{ document.documentElement.setAttribute('data-theme', 'dark'); document.body.classList.remove('light-theme'); if (window.__pr) window.__pr.run('{demo_domain}', {{ sample: true, variant: '{var}', instant: true }}); }}")
            page.wait_for_timeout(600)

            # Auto-open check for critical (DMARC missing)
            if var == "critical":
                is_email_open = page.evaluate("() => document.getElementById('pr-evidence-email-auth').open")
                print(f"[{var}] Email auth accordion auto-open: {is_email_open}")
                assert is_email_open, "Email auth accordion should auto-open on critical (missing DMARC)!"
                notice_displayed = page.evaluate("() => window.getComputedStyle(document.getElementById('pr-map-email-notice')).display !== 'none'")
                print(f"[{var}] Quiet map email notice visible: {notice_displayed}")
                assert notice_displayed, "Quiet map email notice should be visible when DMARC/SPF is missing!"

            dark_png = os.path.join(ARTIFACTS_DIR, f"variant_{var}_dark.png")
            page.screenshot(path=dark_png, full_page=True)
            print(f"Captured: {dark_png}")

            # ── Light Theme ──
            page.evaluate("() => { document.documentElement.setAttribute('data-theme', 'light'); document.body.classList.add('light-theme'); }")
            page.wait_for_timeout(400)
            light_png = os.path.join(ARTIFACTS_DIR, f"variant_{var}_light.png")
            page.screenshot(path=light_png, full_page=True)
            print(f"Captured: {light_png}")

        # ── 5. Print Layout Testing ─────────────────────────────────────
        print("\n--- TEST E: Print Layout Emulation & Evidence Rendering ---")
        page.emulate_media(media="print")
        page.wait_for_timeout(400)
        print_png = os.path.join(ARTIFACTS_DIR, "print_layout_exposure_report.png")
        page.screenshot(path=print_png, full_page=True)
        print(f"Captured print layout: {print_png}")
        page.emulate_media(media=None)

        # ── 6. Mobile 390px Viewport Check ──────────────────────────────
        print("\n--- TEST F: Mobile (390px) Viewport Check ---")
        mobile_ctx = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_ctx.new_page()
        mobile_page.goto("http://127.0.0.1:5050/exposure-report?sample=default&debug=1", wait_until="domcontentloaded")
        mobile_page.evaluate("() => { if (window.__pr) window.__pr.run('acme.example', { sample: true, variant: 'default', instant: true }); }")
        mobile_page.wait_for_timeout(600)
        mobile_png = os.path.join(ARTIFACTS_DIR, "mobile_390px_variant_default.png")
        mobile_page.screenshot(path=mobile_png, full_page=False)
        print(f"Captured mobile: {mobile_png}")

        mobile_ctx.close()
        ctx.close()
        browser.close()

    print("\n[PASS] ALL PLAYWRIGHT BROWSER VERIFICATIONS PASSED SUCCESSFULLY!")


def test_browser_exposure_report():
    run_browser_verification()


if __name__ == "__main__":
    run_browser_verification()
