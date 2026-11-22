"""Shared email HTML sanitization, plain-text extraction, red-flag annotation, and diff helpers.

Used by both Part C (AI Debrief Report) and Part D (Safe Inbox / Email Preview)
so trigger highlighting and HTML sanitization never diverge.
"""

from html.parser import HTMLParser
import difflib
import html as _html
import re

_VOID_TAGS = frozenset({"br", "hr", "img", "wbr"})

_ALLOWED_TAGS = frozenset({
    "a", "abbr", "b", "blockquote", "br", "code", "div", "em",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img",
    "li", "mark", "ol", "p", "pre", "small", "span", "strong",
    "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
})

_DROP_WITH_CONTENT_TAGS = frozenset({
    "script", "style", "iframe", "frame", "frameset", "object",
    "embed", "applet", "noscript", "template", "svg", "math", "form",
})

_ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel", "style"},
    "img": {"src", "alt", "width", "height", "style"},
    "mark": {"class", "tabindex", "data-trigger", "data-tip"},
}
_GLOBAL_SAFE_ATTRS = frozenset({"class", "style", "align", "valign", "colspan", "rowspan", "cellpadding", "cellspacing", "border"})

# Safe inline CSS properties only (prevents expression(), behavior:, url(javascript:))
_UNSAFE_CSS_RE = re.compile(r"(expression\s*\(|javascript\s*:|vbscript\s*:|behavior\s*:|@import|-moz-binding)", re.IGNORECASE)


def _is_safe_url(url: str, allow_data_image: bool = False, require_abs_for_img: bool = False) -> bool:
    if not url:
        return False
    cleaned = re.sub(r"[\x00-\x20]+", "", url).lower()
    if cleaned.startswith(("javascript:", "vbscript:")):
        return False
    if cleaned.startswith("data:"):
        return bool(allow_data_image and cleaned.startswith("data:image/"))
    if cleaned.startswith(("http://", "https://")):
        return True
    if require_abs_for_img:
        return cleaned.startswith("/static/")
    if cleaned.startswith(("mailto:", "/", "#")):
        return True
    if ":" not in cleaned.split("/", 1)[0]:
        return True
    return False


def _sanitize_style(style_val: str) -> str:
    if not style_val or _UNSAFE_CSS_RE.search(style_val):
        return ""
    return style_val.strip()


class _EmailHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        t = tag.lower()
        if t in _DROP_WITH_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth > 0:
            return
        if t not in _ALLOWED_TAGS:
            return

        if t == "img":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            src_low = attr_map.get("src", "").lower()
            style_low = attr_map.get("style", "").lower()
            if (
                any(tok in src_low for tok in ("track", "open", "pixel", "1x1"))
                or (attr_map.get("width") == "1" and attr_map.get("height") == "1")
                or "display:none" in style_low.replace(" ", "")
            ):
                return

        allowed = _ALLOWED_ATTRS.get(t, set()) | _GLOBAL_SAFE_ATTRS
        clean_attrs: list[str] = []
        has_href = False
        for k, v in attrs:
            kl = k.lower()
            if kl.startswith("on") or kl not in allowed:
                continue
            val = v or ""
            if kl == "href":
                if not _is_safe_url(val, allow_data_image=False):
                    continue
                has_href = True
            elif kl == "src":
                if not _is_safe_url(val, allow_data_image=True, require_abs_for_img=True):
                    continue
            elif kl == "style":
                val = _sanitize_style(val)
                if not val:
                    continue
            elif kl == "target":
                val = "_blank"
            clean_attrs.append(f'{kl}="{_html.escape(val, quote=True)}"')

        if t == "a" and has_href:
            if not any(a.startswith("rel=") for a in clean_attrs):
                clean_attrs.append('rel="noopener noreferrer"')

        attr_str = (" " + " ".join(clean_attrs)) if clean_attrs else ""
        self.out.append(f"<{t}{attr_str}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        t = tag.lower()
        if t in _DROP_WITH_CONTENT_TAGS:
            return
        if self._drop_depth > 0:
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in _DROP_WITH_CONTENT_TAGS:
            if self._drop_depth > 0:
                self._drop_depth -= 1
            return
        if self._drop_depth > 0 or t not in _ALLOWED_TAGS or t in _VOID_TAGS:
            return
        self.out.append(f"</{t}>")

    def handle_data(self, data: str):
        if self._drop_depth > 0:
            return
        self.out.append(_html.escape(data, quote=False))

    def handle_entityref(self, name: str):
        if self._drop_depth > 0:
            return
        self.out.append(f"&{name};")

    def handle_charref(self, name: str):
        if self._drop_depth > 0:
            return
        self.out.append(f"&#{name};")

    def handle_comment(self, data: str):
        # Strip HTML comments to prevent conditional-comment or broken-tag smuggling
        return


def sanitize_email_html(raw_html: str | None) -> str:
    """Server-side email HTML sanitizer using an explicit tag/attribute allowlist."""
    if not raw_html or not str(raw_html).strip():
        return ""
    text = str(raw_html)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", text, flags=re.IGNORECASE | re.DOTALL)
    if body_match:
        text = body_match.group(1)

    parser = _EmailHTMLSanitizer()
    parser.feed(text)
    parser.close()
    return "".join(parser.out).strip()


def html_to_plain_text(raw_html: str | None) -> str:
    """Converts email HTML into clean plain text without leaking markup tags."""
    sanitized = sanitize_email_html(raw_html)
    if not sanitized:
        return ""
    # Replace block boundaries with newlines before stripping tags
    text = re.sub(r"<br\s*/?>", "\n", sanitized, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6]|blockquote)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    # Collapse excessive whitespace & blank lines cleanly
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    collapsed = "\n".join(lines)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


_SHARED_TRIGGERS = [
    (
        r"(before\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*today|within\s+\d+\s*(?:hours?|minutes?|days?)|end\s+of\s+(?:the\s+)?day|immediately|urgent(?:ly)?|today\s+to\s+lock\s+in|action\s+required)",
        "Urgency",
        "Urgency: Artificial deadline pressures recipients to act before verifying.",
    ),
    (
        r"(strictly\s+confidential|confidential\s+asset|do\s+not\s+(?:share|discuss|forward)|between\s+us|offsite\s+meeting)",
        "Secrecy",
        "Secrecy: Confidentiality clause isolates the target from consulting peers.",
    ),
    (
        r"(wire\s+transfer|escrow\s+deposit|invoice\s+#?[a-z0-9-]+|overdue\s+(?:balance|invoice)|late\s+penalty|account\s+(?:suspension|lockout)|prevent\s+lockout|suspicious\s+logon)",
        "Loss Aversion",
        "Loss Aversion: Fear of service disruption, lockout, or financial penalty induces clicks.",
    ),
    (
        r"(verify\s+your\s+(?:account|password|identity)|reset\s+(?:your\s+)?password|sign\s+in\s+(?:now|to\s+view)|review\s+and\s+sign|process\s+this\s+invoice|click\s+here)",
        "Credential Phish",
        "Credential Phish: Call-to-action directs targets to an unverified portal.",
    ),
]


def annotate_lure_html(raw_html: str | None) -> str:
    """Sanitizes sent HTML email body and highlights common psychological trigger phrases.

    Shared by both Part C (Why It Worked debrief) and Part D (Safe Inbox 'Show red flags').
    """
    sanitized = sanitize_email_html(raw_html)
    if not sanitized:
        return ""

    parts = re.split(r"(<[^>]+>)", sanitized)
    annotated: list[str] = []
    mark_depth = 0
    for part in parts:
        if part.startswith("<"):
            lower = part.lower()
            if lower.startswith("<mark"):
                mark_depth += 1
            elif lower.startswith("</mark") and mark_depth > 0:
                mark_depth -= 1
            annotated.append(part)
        else:
            if mark_depth > 0:
                annotated.append(part)
                continue
            p_out = part
            for pattern, label, tip in _SHARED_TRIGGERS:
                # Skip matches inside already-inserted <mark> elements on this text node
                segments = re.split(r"(<mark[^>]*>.*?</mark>)", p_out, flags=re.IGNORECASE | re.DOTALL)
                rebuilt = []
                for seg in segments:
                    if seg.lower().startswith("<mark"):
                        rebuilt.append(seg)
                    else:
                        rebuilt.append(
                            re.sub(
                                pattern,
                                lambda m, _lbl=label, _tip=tip: (
                                    f"<mark class='trigger-highlight' tabindex='0' "
                                    f"data-trigger='{_html.escape(_lbl, quote=True)}' "
                                    f"data-tip='{_html.escape(_tip, quote=True)}'>{m.group(0)}</mark>"
                                ),
                                seg,
                                count=1,
                                flags=re.IGNORECASE,
                            )
                        )
                p_out = "".join(rebuilt)
            annotated.append(p_out)
    return "".join(annotated)


def build_sandboxed_email_srcdoc(body_fragment_html: str, show_red_flags: bool = False) -> str:
    """Wraps sanitized (or annotated) email body in a standalone script-free HTML document for iframe srcdoc."""
    content = body_fragment_html or ""
    active_rule = (
        "mark.trigger-highlight { background: rgba(245, 158, 11, 0.28); border-bottom: 2px solid #d97706; color: inherit; border-radius: 3px; padding: 1px 4px; }"
        if show_red_flags
        else "mark.trigger-highlight { background: transparent; border-bottom: 1px dashed rgba(217, 119, 6, 0.55); color: inherit; padding: 0 2px; border-radius: 2px; }"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src http: https: data:; font-src 'self' data:;">
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    padding: 0;
    background: #ffffff;
    color: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    word-break: break-word;
  }}
  body {{ padding: 24px 28px; }}
  p {{ margin: 0 0 14px 0; }}
  p:last-child {{ margin-bottom: 0; }}
  a {{ color: #0066cc; text-decoration: underline; font-weight: 500; }}
  img {{ max-width: 100%; height: auto; }}
  table {{ max-width: 100%; border-collapse: collapse; }}
  mark.trigger-highlight {{
    position: relative;
    cursor: help;
    transition: background-color 0.15s ease;
  }}
  {active_rule}
  mark.trigger-highlight:hover::after,
  mark.trigger-highlight:focus::after {{
    content: attr(data-tip);
    position: fixed;
    left: 16px;
    right: 16px;
    bottom: 12px;
    z-index: 9999;
    background: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12.5px;
    line-height: 1.45;
    box-shadow: 0 10px 25px rgba(2, 6, 23, 0.25);
    pointer-events: none;
  }}
</style>
</head>
<body>{content}</body>
</html>"""


def mask_credential(value: str | None) -> str:
    """Returns masked secret showing only the last 4 characters (never echoes full credential)."""
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if len(s) <= 4:
        return "•" * len(s)
    return ("•" * min(max(len(s) - 4, 4), 12)) + s[-4:]


def compute_email_diff(old_subject: str, old_body_text: str, new_subject: str, new_body_text: str) -> list[dict]:
    """Computes a structured line-by-line diff between old and regenerated emails."""
    old_lines = [f"Subject: {old_subject or ''}", ""] + (old_body_text or "").splitlines()
    new_lines = [f"Subject: {new_subject or ''}", ""] + (new_body_text or "").splitlines()
    diff_rows: list[dict] = []
    for line in difflib.ndiff(old_lines, new_lines):
        prefix = line[:2]
        text = line[2:]
        if prefix == "- ":
            diff_rows.append({"type": "del", "text": text})
        elif prefix == "+ ":
            diff_rows.append({"type": "add", "text": text})
        elif prefix == "  ":
            diff_rows.append({"type": "ctx", "text": text})
    return diff_rows


def plain_mode_badge_info(delivery_mode: str | None) -> dict:
    """Maps internal campaign delivery_mode to a plain-language UI badge."""
    mode = (delivery_mode or "preview").strip().lower()
    if mode in ("mailtrap", "safe_send", "sandbox", "own_mailtrap"):
        return {
            "key": "safe_send",
            "label": "Safe send — delivered to your test inbox",
            "short": "Safe send",
            "tone": "success",
        }
    if mode in ("smtp", "live", "local", "brevo", "resend"):
        return {
            "key": "live",
            "label": "Live — sent to real inboxes",
            "short": "Live",
            "tone": "warning",
        }
    return {
        "key": "preview",
        "label": "Preview — nothing was sent",
        "short": "Preview",
        "tone": "info",
    }


def is_safe_send_mode(delivery_mode: str | None) -> bool:
    return plain_mode_badge_info(delivery_mode)["key"] == "safe_send"


def is_campaign_editable(campaign: dict | None) -> bool:
    """Only draft or preview campaigns allow in-place email editing/re-generation."""
    if not campaign:
        return False
    status = str(campaign.get("status") or "").strip().lower()
    mode = str(campaign.get("delivery_mode") or "").strip().lower()
    return status == "draft" or mode == "preview"


def regenerate_email_content(
    employee_profile: dict,
    scenario: str,
    target_domain: str | None = None,
    prompt_instruction: str = "",
    current_subject: str = "",
    current_body_html: str = "",
    use_ai: bool = True,
) -> dict:
    """Generates or revises a campaign email with optional user prompt instruction.

    Uses OpenRouter AI when configured and `use_ai=True`, with an immediate,
    deterministic prompt-aware fallback so draft/preview editing never fails offline.
    """
    from ai_engine.email_gen import generate_phishing_email, fallback_email, clean_email_data
    import os, json

    instruction = (prompt_instruction or "").strip()
    domain = target_domain or employee_profile.get("company_name") or "company.com"
    recipient_name = employee_profile.get("name") or "Colleague"
    department = employee_profile.get("department") or "Operations"

    result = None
    if use_ai and os.getenv("OPENROUTER_API_KEY"):
        try:
            from ai_engine.email_gen import client as or_client, _fetch_free_models, _STATIC_SAFETY_NET, _text_to_html
            if or_client is not None and instruction:
                fast_client = or_client.with_options(timeout=5.0, max_retries=0)
                models = _fetch_free_models()[:1] or _STATIC_SAFETY_NET[:1]
                sys_msg = (
                    "You rewrite corporate security-awareness phishing simulation drafts according to admin instructions. "
                    "Respond ONLY with JSON matching: {\"subject\": \"...\", \"sender_name\": \"...\", \"body_text\": \"...\"}. "
                    "Preserve the placeholder PHISHING_LINK where the action link belongs. Keep body plain text with paragraph breaks."
                )
                usr_msg = (
                    f"Target: {recipient_name} ({department}) at {domain}. Scenario: {scenario}.\n"
                    f"Current Subject: {current_subject}\n"
                    f"Current Body:\n{html_to_plain_text(current_body_html)}\n\n"
                    f"Admin Revision Prompt: {instruction}"
                )
                for mdl in models[:2]:
                    try:
                        resp = fast_client.chat.completions.create(
                            model=mdl,
                            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": usr_msg}],
                            temperature=0.5,
                            max_tokens=550,
                        )
                        raw = (resp.choices[0].message.content or "").strip()
                        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and parsed.get("body_text"):
                            body_html = _text_to_html(parsed["body_text"])
                            result = clean_email_data({
                                "subject": parsed.get("subject") or current_subject or "Action Required",
                                "sender_name": parsed.get("sender_name") or "IT Security Team",
                                "body_html": body_html,
                                "educational_breakdown": f"Regenerated draft applying: {instruction}",
                            })
                            break
                    except Exception:
                        continue
            elif not instruction:
                result = generate_phishing_email(employee_profile, scenario, target_domain=domain)
        except Exception:
            result = None

    if result is None:
        if instruction:
            base = fallback_email(employee_profile, scenario)
            subj = (current_subject or base.get("subject") or "Action Required").strip()
            plain_curr = html_to_plain_text(current_body_html) if current_body_html else ""
            lower_instr = instruction.lower()
            # Apply deterministic prompt adjustments cleanly so the diff is meaningful
            if "urgent" in lower_instr or "deadline" in lower_instr or "today" in lower_instr or "5 pm" in lower_instr:
                if "urgent" not in subj.lower() and "action required" not in subj.lower():
                    subj = f"Urgent: {subj}"
            elif "short" in lower_instr or "concise" in lower_instr or "brief" in lower_instr:
                subj = subj.replace("Confidential: ", "").replace("Action Required: ", "")

            lead_note = ""
            if "q4" in lower_instr or "audit" in lower_instr:
                lead_note = f"As part of the Q4 internal audit for the {department} team, please complete this review before 5:00 PM today."
            elif "short" in lower_instr or "brief" in lower_instr:
                lead_note = f"Hi {recipient_name}, quick reminder for {department}: please verify your record immediately."
            elif "cfo" in lower_instr or "finance" in lower_instr or "invoice" in lower_instr:
                lead_note = f"Per instructions from Finance Leadership regarding {domain}, verify the pending remittance before 5:00 PM today."
            else:
                # Weave clean sanitized phrasing from the instruction
                clean_hint = re.sub(r"[\r\n<>]+", " ", instruction).strip().rstrip(".")
                lead_note = f"Update ({department}): {clean_hint}. Please act immediately to prevent access interruption."

            cta_html = "<p>Complete verification securely: <a href='PHISHING_LINK'>Review Secure Portal</a></p>"
            if plain_curr and "short" not in lower_instr and "brief" in lower_instr:
                first_para = plain_curr.splitlines()[0] if plain_curr.splitlines() else f"Hi {recipient_name},"
                new_body_html = (
                    f"<p>{_html.escape(first_para)}</p>"
                    f"<p>{_html.escape(lead_note)}</p>"
                    f"{cta_html}"
                    f"<p>Regards,<br>Security &amp; Compliance Desk ({_html.escape(domain)})</p>"
                )
            else:
                new_body_html = (
                    f"<p>Hi {_html.escape(recipient_name)},</p>"
                    f"<p>{_html.escape(lead_note)}</p>"
                    f"{cta_html}"
                    f"<p>Thank you,<br>{_html.escape(base.get('sender_name') or 'Operations Desk')}</p>"
                )
            result = {
                "subject": subj,
                "sender_name": base.get("sender_name") or "Operations Desk",
                "body_html": new_body_html,
                "educational_breakdown": f"Draft updated per prompt: {instruction}",
            }
        else:
            result = fallback_email(employee_profile, scenario)
            if "PHISHING_LINK" not in (result.get("body_html") or "") and "TRACKING_LINK" not in (result.get("body_html") or ""):
                result["body_html"] = (result.get("body_html") or "") + "<p><a href='PHISHING_LINK'>Verify Account</a></p>"

    return result
