/**
 * ════════════════════════════════════════════════════════════════
 * START WITH WHAT YOU'RE HOLDING — INTERACTIVE SHOWPIECE STAGE
 * PhishSim AI Defensive Intelligence Stage Controller
 * All dynamic elements created strictly via DOM APIs (no innerHTML)
 * ════════════════════════════════════════════════════════════════
 */

(function () {
  'use strict';

  // Domain cleaning & validation functions (Mirrored from PhishRecon)
  function cleanDomainInput(raw) {
    if (typeof raw !== 'string') return '';
    var str = raw.trim();
    if (str.indexOf('@') !== -1) {
      str = str.split('@').pop().trim();
    }
    str = str.replace(/^[a-z]+:\/\//i, '');
    str = str.replace(/^\/\//, '');
    str = str.replace(/^[^/@:]+:[^/@:]+@/, '');
    str = str.replace(/[/?#].*$/, '');
    str = str.replace(/:\d+$/, '');
    str = str.replace(/^www\./i, '');
    str = str.replace(/^\.+|\.+$/g, '');
    return str.toLowerCase();
  }

  var DOMAIN_VALIDATION_REGEX = /^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$/;

  // Active timers for vignette animations
  var currentAnimationTimers = [];

  function clearVignetteTimers() {
    for (var i = 0; i < currentAnimationTimers.length; i++) {
      clearTimeout(currentAnimationTimers[i]);
    }
    currentAnimationTimers = [];
  }

  function isReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // Helper to create element with classes and text
  function el(tag, classNames, text) {
    var elem = document.createElement(tag);
    if (classNames) {
      if (Array.isArray(classNames)) {
        for (var i = 0; i < classNames.length; i++) {
          if (classNames[i]) elem.classList.add(classNames[i]);
        }
      } else {
        elem.className = classNames;
      }
    }
    if (text !== undefined && text !== null) {
      elem.textContent = text;
    }
    return elem;
  }

  // Helper for SVG elements
  function svgEl(tag, attrs) {
    var elem = document.createElementNS('http://www.w3.org/2000/svg', tag);
    if (attrs) {
      for (var k in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, k)) {
          elem.setAttribute(k, attrs[k]);
        }
      }
    }
    return elem;
  }

  // ════════════════════════════════════════════════════════════════
  // VIGNETTE BUILDERS (DOM APIs ONLY)
  // ════════════════════════════════════════════════════════════════

  // 1. EMAIL VIGNETTE
  function buildEmailVignette(container) {
    container.textContent = ''; // clear

    var metaStrip = el('div', 'email-meta-strip');
    var rowFrom = el('div', 'email-meta-row');
    rowFrom.appendChild(el('span', 'email-meta-label', 'From:'));
    var senderVal = el('span', ['email-meta-val', 'email-cue'], 'ceo-exec@acme-verify.com');
    rowFrom.appendChild(senderVal);
    metaStrip.appendChild(rowFrom);

    var rowSubj = el('div', 'email-meta-row');
    rowSubj.appendChild(el('span', 'email-meta-label', 'Subject:'));
    rowSubj.appendChild(el('span', 'email-meta-val', 'Urgent: Wire confirmation required #8921'));
    metaStrip.appendChild(rowSubj);

    container.appendChild(metaStrip);

    var bodyBox = el('div', 'email-body-content');
    var urgencySpan = el('span', ['email-cue'], 'Immediate wire transfer of $42,500 required before 5:00 PM today');
    var linkSpan = el('span', ['email-cue'], 'https://acme-finance.billing-auth.top/wire');

    bodyBox.appendChild(urgencySpan);
    bodyBox.appendChild(document.createTextNode(' for pending cloud service renewal. Please review payment voucher and verify banking details at '));
    bodyBox.appendChild(linkSpan);
    bodyBox.appendChild(document.createTextNode('. Do not delay as services suspend at close of business.'));

    container.appendChild(bodyBox);

    var verdictBox = el('div', 'holding-verdict-box');
    var verdictP = el('p', 'holding-verdict-sentence', '"Spoofed executive identity with synthetic financial urgency and an unverified external credential destination."');
    var verdictMeta = el('div', 'holding-verdict-meta');
    var riskPill = el('span', ['holding-pill-risk'], 'High Risk · Score: 88/100');
    var detailText = el('span', null, 'DMARC Fail · SPF SoftFail · Reply-To mismatch');

    verdictMeta.appendChild(riskPill);
    verdictMeta.appendChild(detailText);
    verdictBox.appendChild(verdictP);
    verdictBox.appendChild(verdictMeta);

    container.appendChild(verdictBox);

    // Orchestrated single sequence (2 to 3 seconds)
    if (isReducedMotion()) {
      urgencySpan.classList.add('is-flagged-urgency');
      senderVal.classList.add('is-flagged-sender');
      linkSpan.classList.add('is-flagged-link');
    } else {
      currentAnimationTimers.push(setTimeout(function () {
        urgencySpan.classList.add('is-flagged-urgency');
      }, 700));

      currentAnimationTimers.push(setTimeout(function () {
        senderVal.classList.add('is-flagged-sender');
      }, 1400));

      currentAnimationTimers.push(setTimeout(function () {
        linkSpan.classList.add('is-flagged-link');
      }, 2100));
    }
  }

  // 2. LINK VIGNETTE
  function buildLinkVignette(container) {
    container.textContent = '';

    var flow = el('div', 'link-tracer-flow');

    var inputDisplay = el('div', 'link-input-display');
    inputDisplay.appendChild(el('span', null, 'Tested shortened link:'));
    inputDisplay.appendChild(el('span', 'link-input-pill', 'https://bit.ly/3x8Qp9'));
    flow.appendChild(inputDisplay);

    var grid = el('div', 'link-chain-grid');

    // Hop 1
    var hop1 = el('div', ['link-hop-card']);
    hop1.appendChild(el('span', 'link-hop-badge', 'Hop 1'));
    hop1.appendChild(el('span', 'link-hop-host', 'bit.ly/3x8Qp9'));
    hop1.appendChild(el('span', 'link-hop-status', '301 Moved Permanently'));
    grid.appendChild(hop1);

    // Hop 2
    var hop2 = el('div', ['link-hop-card']);
    hop2.appendChild(el('span', 'link-hop-badge', 'Hop 2'));
    hop2.appendChild(el('span', 'link-hop-host', 't.co/redirect?id=912'));
    hop2.appendChild(el('span', 'link-hop-status', '302 Found'));
    grid.appendChild(hop2);

    // Hop 3 (Destination)
    var hop3 = el('div', ['link-hop-card', 'is-destination']);
    hop3.appendChild(el('span', 'link-hop-badge', 'Final Destination'));
    hop3.appendChild(el('span', 'link-hop-host', 'secure-login-portal.top/auth'));
    hop3.appendChild(el('span', 'link-hop-status', 'Flagged · URLhaus Match'));
    grid.appendChild(hop3);

    flow.appendChild(grid);
    container.appendChild(flow);

    var verdictBox = el('div', 'holding-verdict-box');
    var verdictP = el('p', 'holding-verdict-sentence', '"Multi-hop evasion chain routing through two public shorteners to conceal an unindexed credential-harvesting endpoint."');
    var verdictMeta = el('div', 'holding-verdict-meta');
    var riskPill = el('span', ['holding-pill-risk'], 'Dangerous · Blocked');
    var detailText = el('span', null, '2 hops resolved · SSL: Let\'s Encrypt (Issued 2d ago)');

    verdictMeta.appendChild(riskPill);
    verdictMeta.appendChild(detailText);
    verdictBox.appendChild(verdictP);
    verdictBox.appendChild(verdictMeta);

    container.appendChild(verdictBox);

    if (isReducedMotion()) {
      hop1.classList.add('is-drawn');
      hop2.classList.add('is-drawn');
      hop3.classList.add('is-drawn');
    } else {
      hop1.classList.add('is-drawn');
      currentAnimationTimers.push(setTimeout(function () {
        hop2.classList.add('is-drawn');
      }, 700));

      currentAnimationTimers.push(setTimeout(function () {
        hop3.classList.add('is-drawn');
      }, 1500));
    }
  }

  // 3. PASSWORD VIGNETTE
  function buildPasswordVignette(container) {
    container.textContent = '';

    var wrap = el('div', 'pass-simulation-wrap');

    var inputRow = el('div', 'pass-input-row');
    inputRow.appendChild(el('span', 'pass-count-label', 'Tested credential:'));
    var mockField = el('span', 'pass-field-mock', '••••••••••••');
    inputRow.appendChild(mockField);
    wrap.appendChild(inputRow);

    var hashDiag = el('div', 'pass-hash-diagram');
    var hashLabel = el('span', 'pass-count-label', 'Local client computation (SHA-1):');
    var hashString = el('div', 'pass-hash-string');

    var kPrefix = el('span', 'pass-hash-prefix', '5BAA6');
    var kSuffix = el('span', null, ' 1E4C9 B93F3 F0682 250B6 CF833 1B7EE 68FD8');

    hashString.appendChild(kPrefix);
    hashString.appendChild(kSuffix);
    hashDiag.appendChild(hashLabel);
    hashDiag.appendChild(hashString);

    var noteLeaving = el('div', 'pass-count-label');
    noteLeaving.appendChild(document.createTextNode('Only '));
    var k5Tag = el('span', 'pass-hash-prefix', '5BAA6');
    noteLeaving.appendChild(k5Tag);
    noteLeaving.appendChild(document.createTextNode(' (first 5 characters) leaves your browser via k-anonymity query.'));
    hashDiag.appendChild(noteLeaving);

    wrap.appendChild(hashDiag);

    var counterRow = el('div', 'pass-breach-counter');
    var countNum = el('span', 'pass-count-num', '3,841,209');
    var countLabel = el('span', 'pass-count-label', 'times exposed in known data breaches (Example)');
    counterRow.appendChild(countNum);
    counterRow.appendChild(countLabel);
    wrap.appendChild(counterRow);

    var plainP = el('p', 'pass-k-plain', 'Your full password never leaves your browser; only a five-character hash prefix is queried against breach databases.');
    wrap.appendChild(plainP);

    container.appendChild(wrap);

    var verdictBox = el('div', 'holding-verdict-box');
    var verdictP = el('p', 'holding-verdict-sentence', '"High breach recurrence: this credential appears across multiple public leaks and should not be reused."');
    var verdictMeta = el('div', 'holding-verdict-meta');
    var riskPill = el('span', ['holding-pill-risk'], 'Compromised');
    var detailText = el('span', null, 'k-Anonymity Verified · HaveIBeenPwned API model');

    verdictMeta.appendChild(riskPill);
    verdictMeta.appendChild(detailText);
    verdictBox.appendChild(verdictP);
    verdictBox.appendChild(verdictMeta);

    container.appendChild(verdictBox);

    if (!isReducedMotion()) {
      mockField.textContent = '••••';
      currentAnimationTimers.push(setTimeout(function () {
        mockField.textContent = '••••••••';
      }, 400));
      currentAnimationTimers.push(setTimeout(function () {
        mockField.textContent = '••••••••••••';
      }, 800));
    }
  }

  // 4. COMPANY DOMAIN VIGNETTE (PhishRecon Miniature)
  function buildDomainVignette(container) {
    container.textContent = '';

    var wrap = el('div', 'domain-stage-wrap');

    var svgWrap = el('div', 'domain-svg-container');
    var svg = svgEl('svg', {
      viewBox: '0 0 440 220',
      class: 'domain-mini-svg',
      'aria-label': 'Audited attack surface map example for acme.example'
    });

    // Defs for center gradient
    var defs = svgEl('defs');
    var grad = svgEl('radialGradient', { id: 'mini-center-glow', cx: '50%', cy: '50%', r: '50%' });
    grad.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#00f0ff', 'stop-opacity': '0.35' }));
    grad.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#00f0ff', 'stop-opacity': '0' }));
    defs.appendChild(grad);
    svg.appendChild(defs);

    var cx = 220;
    var cy = 110;

    // Rings
    var ring1 = svgEl('circle', { cx: cx, cy: cy, r: 42, class: 'pr-mini-ring' });
    var ring2 = svgEl('circle', { cx: cx, cy: cy, r: 70, class: 'pr-mini-ring' });
    var ring3 = svgEl('circle', { cx: cx, cy: cy, r: 96, class: 'pr-mini-ring' });

    svg.appendChild(ring1);
    svg.appendChild(ring2);
    svg.appendChild(ring3);

    // Center disc
    var centerGlow = svgEl('circle', { cx: cx, cy: cy, r: 34, fill: 'url(#mini-center-glow)' });
    var centerCircle = svgEl('circle', { cx: cx, cy: cy, r: 24, fill: '#0a101d', stroke: '#00f0ff', 'stroke-width': '1.5' });
    var centerText = svgEl('text', {
      x: cx,
      y: cy + 4,
      'text-anchor': 'middle',
      fill: '#ffffff',
      'font-family': 'JetBrains Mono, monospace',
      'font-size': '10',
      'font-weight': '700'
    });
    centerText.textContent = 'acme';

    svg.appendChild(centerGlow);
    svg.appendChild(centerCircle);
    svg.appendChild(centerText);

    // Nodes
    // Ring 1: TLS / Registrar
    var nodeTLS = svgEl('circle', { cx: cx - 36, cy: cy - 20, r: 4, fill: '#10b981', class: 'pr-mini-node' });
    var labelTLS = svgEl('text', { x: cx - 44, y: cy - 22, 'text-anchor': 'end', fill: '#94a3b8', 'font-size': '8', 'font-family': 'monospace', class: 'pr-mini-node' });
    labelTLS.textContent = 'TLS Valid';

    // Ring 2: SPF / DMARC
    var nodeSPF = svgEl('circle', { cx: cx + 62, cy: cy - 30, r: 4, fill: '#10b981', class: 'pr-mini-node' });
    var nodeDMARC = svgEl('circle', { cx: cx - 58, cy: cy + 38, r: 4, fill: '#f59e0b', class: 'pr-mini-node' });
    var labelDMARC = svgEl('text', { x: cx - 66, y: cy + 42, 'text-anchor': 'end', fill: '#f59e0b', 'font-size': '8', 'font-family': 'monospace', class: 'pr-mini-node' });
    labelDMARC.textContent = 'DMARC None';

    // Ring 3: Subdomains & Look-alike
    var nodeSub1 = svgEl('circle', { cx: cx + 80, cy: cy + 46, r: 4, fill: '#00f0ff', class: 'pr-mini-node' });
    var labelSub1 = svgEl('text', { x: cx + 90, y: cy + 50, 'text-anchor': 'start', fill: '#94a3b8', 'font-size': '8', 'font-family': 'monospace', class: 'pr-mini-node' });
    labelSub1.textContent = 'vpn.acme.example';

    var nodeLook = svgEl('circle', { cx: cx, cy: cy - 96, r: 5, fill: '#ef4444', class: 'pr-mini-node' });
    var labelLook = svgEl('text', { x: cx, y: cy - 104, 'text-anchor': 'middle', fill: '#f87171', 'font-size': '8.5', 'font-weight': 'bold', 'font-family': 'monospace', class: 'pr-mini-node' });
    labelLook.textContent = 'acme-security.com (Resolves)';

    svg.appendChild(nodeTLS);
    svg.appendChild(labelTLS);
    svg.appendChild(nodeSPF);
    svg.appendChild(nodeDMARC);
    svg.appendChild(labelDMARC);
    svg.appendChild(nodeSub1);
    svg.appendChild(labelSub1);
    svg.appendChild(nodeLook);
    svg.appendChild(labelLook);

    svgWrap.appendChild(svg);
    wrap.appendChild(svgWrap);

    var verdictBox = el('div', 'holding-verdict-box');
    var verdictP = el('p', 'holding-verdict-sentence', '"Core infrastructure is properly configured, but look-alike domain resolution and missing DMARC enforcement increase impersonation exposure."');
    var verdictMeta = el('div', 'holding-verdict-meta');
    var scorePill = el('span', ['holding-pill-risk', 'pill-warning'], 'Exposure: 42/100');
    var detailText = el('span', null, '3 subdomains mapped · 1 active resolving look-alike (Example)');

    verdictMeta.appendChild(scorePill);
    verdictMeta.appendChild(detailText);
    verdictBox.appendChild(verdictP);
    verdictBox.appendChild(verdictMeta);

    wrap.appendChild(verdictBox);
    container.appendChild(wrap);

    var miniNodes = [nodeTLS, labelTLS, nodeSPF, nodeDMARC, labelDMARC, nodeSub1, labelSub1, nodeLook, labelLook];

    if (isReducedMotion()) {
      ring1.classList.add('is-drawn');
      ring2.classList.add('is-drawn');
      ring3.classList.add('is-drawn');
      for (var j = 0; j < miniNodes.length; j++) {
        miniNodes[j].classList.add('is-visible');
      }
    } else {
      currentAnimationTimers.push(setTimeout(function () {
        ring1.classList.add('is-drawn');
        nodeTLS.classList.add('is-visible');
        labelTLS.classList.add('is-visible');
      }, 400));

      currentAnimationTimers.push(setTimeout(function () {
        ring2.classList.add('is-drawn');
        nodeSPF.classList.add('is-visible');
        nodeDMARC.classList.add('is-visible');
        labelDMARC.classList.add('is-visible');
      }, 1000));

      currentAnimationTimers.push(setTimeout(function () {
        ring3.classList.add('is-drawn');
        nodeSub1.classList.add('is-visible');
        labelSub1.classList.add('is-visible');
        nodeLook.classList.add('is-visible');
        labelLook.classList.add('is-visible');
      }, 1700));
    }
  }

  // ════════════════════════════════════════════════════════════════
  // STAGE CONTROLLER
  // ════════════════════════════════════════════════════════════════

  function initHoldingSection() {
    var section = document.getElementById('threat-intel-suite');
    if (!section) return;

    var tabs = section.querySelectorAll('.holding-tab-item');
    var panels = section.querySelectorAll('.holding-panel');
    var stageTitle = document.getElementById('holding-stage-title');

    var toolTitles = {
      email: 'Email forensics',
      link: 'URL destination tracer',
      password: 'K-anonymity credential check',
      domain: 'Perimeter attack surface map'
    };

    function activateTab(targetKey, focusTab) {
      clearVignetteTimers();

      // Update tabs & row wrappers
      for (var i = 0; i < tabs.length; i++) {
        var t = tabs[i];
        var isMatch = t.getAttribute('data-target') === targetKey;
        t.classList.toggle('is-active', isMatch);
        t.setAttribute('aria-selected', isMatch ? 'true' : 'false');
        t.setAttribute('tabindex', isMatch ? '0' : '-1');
        var rowParent = t.closest('.holding-tab-row');
        if (rowParent) {
          rowParent.classList.toggle('is-active', isMatch);
        }
        if (isMatch && focusTab) {
          t.focus();
        }
      }

      // Update panels & stage title
      if (stageTitle && toolTitles[targetKey]) {
        stageTitle.textContent = toolTitles[targetKey];
      }

      for (var j = 0; j < panels.length; j++) {
        var p = panels[j];
        var isPanelMatch = p.getAttribute('data-panel') === targetKey;
        p.classList.toggle('is-active', isPanelMatch);
        if (isPanelMatch) {
          p.removeAttribute('hidden');
          // Build vignette content with DOM APIs
          if (targetKey === 'email') buildEmailVignette(p);
          else if (targetKey === 'link') buildLinkVignette(p);
          else if (targetKey === 'password') buildPasswordVignette(p);
          else if (targetKey === 'domain') buildDomainVignette(p);
        } else {
          p.setAttribute('hidden', 'true');
          p.textContent = ''; // clear unmounted panel
        }
      }
    }

    // ── Scroll-Driven Progress (Desktop >= 1000px Only) ──
    var isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    var userManualSelection = false;
    var resumeScrollTimer = null;

    function lockManualSelection() {
      userManualSelection = true;
      clearTimeout(resumeScrollTimer);
      resumeScrollTimer = setTimeout(function () {
        userManualSelection = false;
      }, 1500);
    }

    function handleScrollProgress() {
      if (isTouch || window.innerWidth < 1000 || userManualSelection) return;
      var rect = section.getBoundingClientRect();
      var windowHeight = window.innerHeight || 800;

      // When section top is above or near navbar (top <= 120px)
      if (rect.top > 140) {
        var currentActiveAbove = section.querySelector('.holding-tab-item.is-active');
        if (currentActiveAbove && currentActiveAbove.getAttribute('data-target') !== 'email') {
          activateTab('email', false);
        }
        return;
      }

      var totalScrollable = rect.height - windowHeight;
      if (totalScrollable <= 0) return;

      var scrolled = 120 - rect.top;
      var progress = Math.max(0, Math.min(0.999, scrolled / totalScrollable));

      var stepKeys = ['email', 'link', 'password', 'domain'];
      var targetIdx = Math.min(3, Math.floor(progress * 4));
      var targetKey = stepKeys[targetIdx];

      var currentActive = section.querySelector('.holding-tab-item.is-active');
      var curKey = currentActive ? currentActive.getAttribute('data-target') : null;

      if (targetKey && targetKey !== curKey) {
        activateTab(targetKey, false);
      }
    }

    window.addEventListener('scroll', handleScrollProgress, { passive: true });

    // Tab Click handlers
    for (var k = 0; k < tabs.length; k++) {
      (function (tab) {
        tab.addEventListener('click', function (e) {
          // If clicked on the tool link span, navigate to the tool
          var toolLink = e.target.closest('.holding-tab-link');
          if (toolLink) {
            e.preventDefault();
            e.stopPropagation();
            var href = toolLink.getAttribute('data-href');
            if (href) {
              window.location.href = href;
              return;
            }
          }

          e.preventDefault();
          lockManualSelection();
          var target = tab.getAttribute('data-target');
          activateTab(target, false);
        });
      })(tabs[k]);
    }

    // Keyboard navigation (Arrow keys, Home, End)
    var tablist = document.getElementById('holding-tablist');
    if (tablist) {
      tablist.addEventListener('keydown', function (e) {
        var tabArr = Array.prototype.slice.call(tabs);
        var curIdx = tabArr.indexOf(document.activeElement);
        if (curIdx === -1) return;

        var nextIdx = -1;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
          e.preventDefault();
          nextIdx = (curIdx + 1) % tabArr.length;
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
          e.preventDefault();
          nextIdx = (curIdx - 1 + tabArr.length) % tabArr.length;
        } else if (e.key === 'Home') {
          e.preventDefault();
          nextIdx = 0;
        } else if (e.key === 'End') {
          e.preventDefault();
          nextIdx = tabArr.length - 1;
        }

        if (nextIdx !== -1) {
          lockManualSelection();
          var target = tabArr[nextIdx].getAttribute('data-target');
          activateTab(target, true);
        }
      });
    }

    // ── Domain Input Form Validation & Navigation ──
    var domainForm = document.getElementById('holding-domain-form');
    var domainInput = document.getElementById('holding-domain-input');
    var domainError = document.getElementById('holding-domain-error');

    if (domainForm && domainInput) {
      domainForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var raw = domainInput.value || '';
        var cleaned = cleanDomainInput(raw);

        if (!cleaned) {
          showDomainError('Please enter a company domain name to audit.');
          return;
        }

        if (!DOMAIN_VALIDATION_REGEX.test(cleaned)) {
          showDomainError('Invalid domain format. Enter a valid domain like acme.com or corp.co.uk.');
          return;
        }

        // Clear error and navigate
        if (domainError) {
          domainError.textContent = '';
          domainError.style.display = 'none';
        }

        // Navigate cleanly to exposure report with domain query parameter
        window.location.href = '/exposure-report?domain=' + encodeURIComponent(cleaned);
      });

      domainInput.addEventListener('input', function () {
        if (domainError && domainError.style.display !== 'none') {
          domainError.textContent = '';
          domainError.style.display = 'none';
        }
      });
    }

    function showDomainError(msg) {
      if (!domainError) return;
      domainError.textContent = msg;
      domainError.style.display = 'block';
      if (domainInput) {
        domainInput.focus();
      }
    }

    // Initialize with default 'email' tab
    activateTab('email', false);
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHoldingSection);
  } else {
    initHoldingSection();
  }
})();
