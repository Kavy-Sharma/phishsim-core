import json
import os
import socket
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import (
    app,
    is_safe_ip,
    is_safe_url,
    normalize_exposure_domain,
    calculate_exposure_score,
    EXPOSURE_WEIGHTS,
    check_lookalikes,
    probe_exact_lookalike_ip,
    check_email_auth,
    _count_spf_lookups_and_parse,
)
from osint.scraper import safe_fetch_url


# ────────────────────────────────────────────────────────────────
# 1. Domain Normalisation & Rejection Tests
# ────────────────────────────────────────────────────────────────
class TestDomainNormalisation(unittest.TestCase):
    def test_accepted_domains(self):
        cases = [
            ("example.com", "example.com"),
            ("https://www.Example.com:443/x", "example.com"),
            ("http://SUB.DOMAIN.CO.UK/path?query=1#frag", "sub.domain.co.uk"),
            ("user:pass@example.org", "example.org"),
            ("  test-domain.net  ", "test-domain.net"),
            ("HTTP://WWW.TEST.COM", "test.com"),
        ]
        for raw, expected in cases:
            norm = normalize_exposure_domain(raw)
            self.assertEqual(norm, expected, f"Failed for {raw}")

    def test_rejected_payloads(self):
        rejected = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "127.0.0.1",
            "192.168.1.1",
            "10.0.0.5",
            "169.254.169.254",
            "[::1]",
            "::1",
            "localhost",
            "localhost.localdomain",
            "corp.local",
            "mycompany.internal",
            "test.lan",
            "%.example.com",
            "%",
            "example.com' OR 1=1--",
            "",
            "   ",
            "not-a-domain",
            "http:///example.com",
        ]
        for raw in rejected:
            norm = normalize_exposure_domain(raw)
            self.assertIsNone(norm, f"Payload should have been rejected (returned None): {raw}")


# ────────────────────────────────────────────────────────────────
# 2. Scoring Combinations & "Not Enough Data" Threshold Tests
# ────────────────────────────────────────────────────────────────
class TestScoringThresholds(unittest.TestCase):
    def setUp(self):
        self.ok_rdap = {"status": "ok", "domain_age_days": 1000}
        self.ok_ssl = {"status": "ok", "valid": True}
        self.ok_look = {"status": "ok", "live_lookalikes": []}
        self.ok_subs = {"status": "ok", "total": 0, "subdomains": []}
        self.ok_surf = {"status": "ok", "emails": [], "socials": {}}
        self.ok_email = {"status": "ok", "points": 0, "spf": {"status": "strict"}, "dmarc": {"status": "reject"}}

        self.unavail = {"status": "unavailable"}

    def test_weights_sum_to_100(self):
        total = sum(EXPOSURE_WEIGHTS.values())
        self.assertEqual(total, 100)
        self.assertEqual(EXPOSURE_WEIGHTS["lookalikes"], 25)
        self.assertEqual(EXPOSURE_WEIGHTS["email_auth"], 25)
        self.assertEqual(EXPOSURE_WEIGHTS["domain_age"], 15)
        self.assertEqual(EXPOSURE_WEIGHTS["ssl"], 15)
        self.assertEqual(EXPOSURE_WEIGHTS["subdomains"], 10)
        self.assertEqual(EXPOSURE_WEIGHTS["surface"], 10)

    def test_all_complete(self):
        # 2000 days domain age -> 0 pts
        ok_rdap = {"status": "ok", "domain_age_days": 2000}
        score, posture, breakdown, incomplete = calculate_exposure_score(
            ok_rdap, self.ok_ssl, self.ok_look, self.ok_subs, self.ok_surf, self.ok_email
        )
        self.assertIsNotNone(score)
        self.assertEqual(score, 0)
        self.assertEqual(posture, "Low risk")
        self.assertEqual(len(incomplete), 0)

    def test_all_unavailable(self):
        score, posture, breakdown, incomplete = calculate_exposure_score(
            self.unavail, self.unavail, self.unavail, self.unavail, self.unavail, self.unavail
        )
        self.assertIsNone(score)
        self.assertEqual(posture, "Not enough data")
        self.assertEqual(len(incomplete), 6)

    def test_threshold_below_50(self):
        # Lookalikes (25) + Subdomains (10) + Surface (10) = 45 assessable points (< 50)
        score, posture, breakdown, incomplete = calculate_exposure_score(
            self.unavail, self.unavail, self.ok_look, self.ok_subs, self.ok_surf, self.unavail
        )
        self.assertIsNone(score)
        self.assertEqual(posture, "Not enough data")
        inc_lower = [s.lower() for s in incomplete]
        self.assertTrue(any("domain" in s for s in inc_lower))
        self.assertTrue(any("tls" in s or "ssl" in s for s in inc_lower))
        self.assertTrue(any("email" in s for s in inc_lower))

    def test_threshold_at_50(self):
        # Lookalikes (25) + Email auth (25) = 50 assessable points (>= 50)
        score, posture, breakdown, incomplete = calculate_exposure_score(
            self.unavail, self.unavail, self.ok_look, self.unavail, self.unavail, self.ok_email
        )
        self.assertIsNotNone(score)
        self.assertNotEqual(posture, "Not enough data")

    def test_threshold_at_55(self):
        # Email auth (25) + Domain age (15) + TLS (15) = 55 assessable points (>= 50)
        score, posture, breakdown, incomplete = calculate_exposure_score(
            self.ok_rdap, self.ok_ssl, self.unavail, self.unavail, self.unavail, self.ok_email
        )
        self.assertIsNotNone(score)
        self.assertNotEqual(posture, "Not enough data")

    def test_exact_49_points_simulation(self):
        # Temporarily mock weights to test exact 49 vs 50 boundary
        with patch.dict(EXPOSURE_WEIGHTS, {"lookalikes": 49, "domain_age": 1}):
            score, posture, _, _ = calculate_exposure_score(
                self.unavail, self.unavail, self.ok_look, self.unavail, self.unavail, self.unavail
            )
            self.assertIsNone(score)
            self.assertEqual(posture, "Not enough data")

            score50, posture50, _, _ = calculate_exposure_score(
                self.ok_rdap, self.unavail, self.ok_look, self.unavail, self.unavail, self.unavail
            )
            self.assertIsNotNone(score50)
            self.assertNotEqual(posture50, "Not enough data")
            self.assertIsNotNone(score50)
            self.assertNotEqual(posture50, "Not enough data")


# ────────────────────────────────────────────────────────────────
# 3. SSRF & Safe IP Validation Tests (A1 & A2)
# ────────────────────────────────────────────────────────────────
class TestSSRFPrevention(unittest.TestCase):
    def test_is_safe_ip_private_and_special(self):
        unsafe_ips = [
            "127.0.0.1",
            "127.0.0.2",
            "169.254.169.254",   # Cloud metadata
            "169.254.1.1",       # Link local
            "10.0.0.5",          # RFC 1918 Class A
            "10.254.254.254",
            "192.168.1.1",       # RFC 1918 Class C
            "172.16.0.9",        # RFC 1918 Class B
            "172.31.255.255",
            "100.64.0.1",        # CGNAT RFC 6598
            "100.127.255.254",   # CGNAT
            "::1",               # IPv6 loopback
            "fc00::1",           # IPv6 Unique Local Address
            "fd12:3456:789a::1", # IPv6 ULA
            "fe80::1",           # IPv6 link-local
            "::ffff:127.0.0.1",  # IPv4-mapped IPv6 loopback
            "::ffff:10.0.0.1",   # IPv4-mapped private
            "::ffff:169.254.169.254",
            "::ffff:100.64.0.1", # IPv4-mapped CGNAT
            "0.0.0.0",
            "255.255.255.255",
            "not-an-ip",         # Fail closed on parse failure
            "",
            None,
        ]
        for ip in unsafe_ips:
            self.assertFalse(is_safe_ip(ip), f"IP should be marked UNSAFE: {ip}")

    def test_is_safe_ip_public(self):
        safe_ips = [
            "93.184.216.34",     # example.com
            "8.8.8.8",
            "1.1.1.1",
            "2606:2800:220:1:248:1893:25c8:1946",
        ]
        for ip in safe_ips:
            self.assertTrue(is_safe_ip(ip), f"IP should be marked SAFE: {ip}")

    def test_is_safe_url_fail_closed(self):
        self.assertFalse(is_safe_url("http://127.0.0.1/"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_url("http://localhost:5000/"))
        self.assertFalse(is_safe_url("http://nonexistent-unresolvable-domain-xyz-12345.com/"))
        self.assertFalse(is_safe_url("not-a-url"))

    @patch("socket.getaddrinfo")
    @patch("socket.create_connection")
    def test_lookalike_private_ip_never_connects(self, mock_connect, mock_getaddrinfo):
        """A candidate resolving to a private IP must never receive any connection."""
        private_ips = ["127.0.0.1", "169.254.169.254", "10.0.0.5", "192.168.1.1", "172.16.0.9", "100.64.0.1"]
        for priv_ip in private_ips:
            mock_connect.reset_mock()
            mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (priv_ip, 80))]

            result = check_lookalikes("example.com", primary_ips=["93.184.216.34"])
            for call in mock_connect.call_args_list:
                dest = call[0][0]
                ip_called = dest[0] if isinstance(dest, tuple) else dest
                self.assertNotEqual(ip_called, priv_ip, f"SSRF! Connected to private IP: {priv_ip}")

    def test_probe_public_ip_does_not_follow_redirects(self):
        """probe_exact_lookalike_ip sends minimal request and never follows redirects."""
        with patch("http.client.HTTPConnection") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn_cls.return_value = mock_conn

            mock_resp = MagicMock()
            mock_resp.status = 301
            mock_resp.read.return_value = b""
            mock_resp.getheader.return_value = "https://example.com/path/to/page"
            mock_conn.getresponse.return_value = mock_resp

            status, code, loc_host, is_brand = probe_exact_lookalike_ip(
                "93.184.216.34", "example-lookalike.com", "example.com"
            )
            self.assertEqual(code, 301)
            self.assertEqual(status, "redirect")
            self.assertTrue(is_brand)
            self.assertEqual(loc_host, "example.com")
            self.assertEqual(mock_conn.request.call_count, 1)

    def test_safe_fetch_url_blocks_redirect_to_private(self):
        """safe_fetch_url must reject redirects pointing to internal addresses."""
        with patch("socket.create_connection") as mock_conn, \
             patch("socket.getaddrinfo") as mock_dns:
            
            # Hop 1: public IP 93.184.216.34 returns 302 to 169.254.169.254
            mock_dns.side_effect = [
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))],
            ]
            mock_sock1 = MagicMock()
            mock_sock1.recv.side_effect = [
                b"HTTP/1.1 302 Found\r\nLocation: http://169.254.169.254/latest/meta-data/\r\nContent-Length: 0\r\n\r\n",
                b"",
            ]
            mock_conn.return_value.__enter__.return_value = mock_sock1

            result = safe_fetch_url("http://example.com")
            # Redirect to private IP 169.254.169.254 must be refused, returning None
            self.assertIsNone(result)


# ────────────────────────────────────────────────────────────────
# 4. Dead-Resolver & Scraper Failure Tests (B2 & B3)
# ────────────────────────────────────────────────────────────────
class TestFailureSemantics(unittest.TestCase):
    @patch("socket.gethostbyname_ex")
    def test_dead_resolver_reports_unavailable(self, mock_gethostbyname_ex):
        """If audited domain AND candidates fail to resolve, report unavailable not ok."""
        mock_gethostbyname_ex.side_effect = socket.gaierror("Name or service not known")
        res = check_lookalikes("example.com", primary_ips=[])
        self.assertEqual(res["status"], "unavailable")

    def test_scraper_failure_marks_surface_unavailable(self):
        """A scraper error returns fetch_success=False and maps to unavailable."""
        from osint.scraper import scrape_company
        with patch("osint.scraper.safe_fetch_url", return_value=None):
            prof = scrape_company("unreachable-site-xyz.com")
            self.assertFalse(prof.get("fetch_success"))


# ────────────────────────────────────────────────────────────────
# 5. NDJSON Stream & API Integration Tests
# ────────────────────────────────────────────────────────────────
class TestExposureReportAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ndjson_stream_stage_order_and_content_type(self):
        """Verify NDJSON stream stages and application/x-ndjson content type."""
        with patch("app.is_safe_ip", return_value=True), \
             patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
            
            resp = self.client.post("/api/exposure-report", data={"domain": "example.com"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.content_type, "application/x-ndjson")

            lines = [json.loads(l) for l in resp.data.decode("utf-8").split("\n") if l.strip()]
            stages = [d.get("stage") for d in lines]
            self.assertEqual(stages[:6], ["domain_ssl", "email_auth", "lookalikes", "subdomains", "exposed_surface", "summary"])

    def test_hostile_strings_returned_inert(self):
        """Verify HTML/script injections in domain or parameters are rejected safely."""
        resp = self.client.post("/api/exposure-report", data={"domain": "<script>alert(1)</script>"})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data.get("success", True))
        self.assertNotIn("<script>", str(data))


# ────────────────────────────────────────────────────────────────
# 6. Email Authentication (SPF, DMARC, MTA-STS, TLS-RPT, MX, DKIM) Tests
# ────────────────────────────────────────────────────────────────
class TestEmailAuthentication(unittest.TestCase):
    def test_spf_all_qualifiers(self):
        # +all -> open, Exposed, 25 points
        def txt_open(name):
            if name == "domain.com":
                return ["v=spf1 include:_spf.domain.com +all"]
            return ["v=spf1 ip4:1.2.3.4 ~all"]
        res_open = check_email_auth("domain.com", txt_resolver_fn=txt_open, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_open["spf"]["status"], "open")
        self.assertEqual(res_open["spf"]["grade"], "Exposed")
        self.assertEqual(res_open["points"], 25)

        # ?all -> neutral, Effectively open
        def txt_neutral(name):
            return ["v=spf1 ?all"]
        res_neutral = check_email_auth("domain.com", txt_resolver_fn=txt_neutral, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_neutral["spf"]["status"], "neutral")
        self.assertEqual(res_neutral["spf"]["grade"], "Effectively open")

        # ~all -> softfail, Soft fail
        def txt_soft(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=reject;"]
            return ["v=spf1 ip4:1.2.3.4 ~all"]
        res_soft = check_email_auth("domain.com", txt_resolver_fn=txt_soft, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_soft["spf"]["status"], "softfail")
        self.assertEqual(res_soft["spf"]["grade"], "Soft fail")
        self.assertLessEqual(res_soft["points"], 5)

        # -all -> strict, Strict
        def txt_strict(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=reject;"]
            return ["v=spf1 ip4:1.2.3.4 -all"]
        res_strict = check_email_auth("domain.com", txt_resolver_fn=txt_strict, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_strict["spf"]["status"], "strict")
        self.assertEqual(res_strict["spf"]["grade"], "Strict")
        self.assertEqual(res_strict["points"], 0)

    def test_spf_lookup_limit_exceeded(self):
        # Chain of 11 includes -> exceeds RFC 7208 10-lookup limit
        records = {
            "domain.com": ["v=spf1 include:s1.domain.com -all"],
            "s1.domain.com": ["v=spf1 include:s2.domain.com -all"],
            "s2.domain.com": ["v=spf1 include:s3.domain.com -all"],
            "s3.domain.com": ["v=spf1 include:s4.domain.com -all"],
            "s4.domain.com": ["v=spf1 include:s5.domain.com -all"],
            "s5.domain.com": ["v=spf1 include:s6.domain.com -all"],
            "s6.domain.com": ["v=spf1 include:s7.domain.com -all"],
            "s7.domain.com": ["v=spf1 include:s8.domain.com -all"],
            "s8.domain.com": ["v=spf1 include:s9.domain.com -all"],
            "s9.domain.com": ["v=spf1 include:s10.domain.com -all"],
            "s10.domain.com": ["v=spf1 include:s11.domain.com -all"],
            "s11.domain.com": ["v=spf1 ip4:1.2.3.4 -all"],
        }
        res = check_email_auth("domain.com", txt_resolver_fn=lambda n: records.get(n, []), mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res["spf"]["status"], "lookup_limit_exceeded")
        self.assertEqual(res["spf"]["grade"], "Broken")
        self.assertGreater(res["spf"]["lookups"], 10)

    def test_spf_duplicate_records(self):
        # Multiple SPF records on domain -> invalid (PermError)
        def txt_dup(name):
            if name == "domain.com":
                return ["v=spf1 ip4:1.2.3.4 -all", "v=spf1 include:_spf.google.com -all"]
            return []
        res = check_email_auth("domain.com", txt_resolver_fn=txt_dup, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res["spf"]["status"], "invalid")
        self.assertEqual(res["spf"]["grade"], "Invalid")
        self.assertTrue(res["spf"]["multiple_records"])

    def test_dmarc_policies_and_pct(self):
        # Missing DMARC
        res_missing = check_email_auth("domain.com", txt_resolver_fn=lambda n: ["v=spf1 -all"] if n == "domain.com" else [], mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_missing["dmarc"]["status"], "missing")
        self.assertEqual(res_missing["dmarc"]["grade"], "Exposed")
        self.assertEqual(res_missing["points"], 25)

        # p=none (monitoring only)
        def txt_none(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=none; rua=mailto:dmarc@domain.com;"]
            return ["v=spf1 -all"]
        res_none = check_email_auth("domain.com", txt_resolver_fn=txt_none, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_none["dmarc"]["status"], "none")
        self.assertEqual(res_none["dmarc"]["grade"], "Monitoring only")
        self.assertEqual(res_none["points"], 18)

        # p=quarantine
        def txt_quar(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=quarantine;"]
            return ["v=spf1 -all"]
        res_quar = check_email_auth("domain.com", txt_resolver_fn=txt_quar, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_quar["dmarc"]["status"], "quarantine")
        self.assertTrue("quarantine" in res_quar["dmarc"]["grade"].lower())

        # p=reject
        def txt_rej(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=reject;"]
            return ["v=spf1 -all"]
        res_rej = check_email_auth("domain.com", txt_resolver_fn=txt_rej, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_rej["dmarc"]["status"], "reject")
        self.assertTrue("reject" in res_rej["dmarc"]["grade"].lower())
        self.assertEqual(res_rej["points"], 0)

        # pct < 100
        def txt_pct(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=reject; pct=50;"]
            return ["v=spf1 -all"]
        res_pct = check_email_auth("domain.com", txt_resolver_fn=txt_pct, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_pct["dmarc"]["pct"], 50)
        self.assertIn("50%", res_pct["dmarc"]["detail"])
        self.assertGreater(res_pct["points"], 0)

    def test_no_mx_domains(self):
        # Clean null-MX domain: (0, ".") with SPF -all and DMARC reject -> 0 points
        def txt_clean_null(name):
            if name == "_dmarc.domain.com":
                return ["v=DMARC1; p=reject;"]
            if name == "domain.com":
                return ["v=spf1 -all"]
            return []
        res_clean = check_email_auth("domain.com", txt_resolver_fn=txt_clean_null, mx_resolver_fn=lambda d: [(0, ".")])
        self.assertFalse(res_clean["has_mx"])
        self.assertTrue(res_clean["is_null_mx"])
        self.assertEqual(res_clean["points"], 0)
        self.assertIn("does not receive mail", res_clean["overall_summary"].lower())

        # No MX records at all, missing DMARC -> 25 points
        res_no_dmarc = check_email_auth("domain.com", txt_resolver_fn=lambda n: ["v=spf1 -all"] if n == "domain.com" else [], mx_resolver_fn=lambda d: [])
        self.assertFalse(res_no_dmarc["has_mx"])
        self.assertEqual(res_no_dmarc["points"], 25)

    def test_dkim_selector_wording_never_overclaims(self):
        # Found selector
        def txt_dkim_found(name):
            if name == "google._domainkey.domain.com":
                return ["v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ..."]
            return []
        res_found = check_email_auth("domain.com", txt_resolver_fn=txt_dkim_found, mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_found["dkim"]["status"], "found")
        self.assertEqual(res_found["dkim"]["selector"], "google")
        self.assertIn("Found for selector 'google'", res_found["dkim"]["detail"])

        # Not found selector -> must NEVER claim absent!
        res_not_found = check_email_auth("domain.com", txt_resolver_fn=lambda n: [], mx_resolver_fn=lambda d: [(10, "mail.domain.com")])
        self.assertEqual(res_not_found["dkim"]["status"], "not_detected")
        self.assertEqual(
            res_not_found["dkim"]["detail"],
            "Not detected with common selectors (this does not mean it's absent)"
        )
