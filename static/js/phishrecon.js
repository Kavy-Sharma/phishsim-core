// ── Single Scoring Weights Source of Truth (B7) ──────────────────
const EXPOSURE_WEIGHTS = {
  lookalikes: 25,
  email_auth: 25,
  domain_age: 15,
  ssl: 15,
  subdomains: 10,
  surface: 10
};



// ── 1. Single State Object ──────────────────────────────────────

// ── Accessibility Live Region Announcer ──────────────────────────
function announceLive(message) {
  const announcer = document.getElementById('pr-live-announcer');
  if (announcer && message) {
    announcer.textContent = '';
    setTimeout(() => {
      announcer.textContent = message;
    }, 60);
  }
}

// ── Neutral Glyph Controller (A4: Zero third-party favicon requests) ──
function createFaviconImageElement(domain, size = 16) {
  const clean = cleanDomainInput(domain);
  return createLetterGlyphSvg(clean, size);
}

function createLetterGlyphSvg(domain, size = 16) {
  const letter = (domain.replace(/^www\./i, '')[0] || 'D').toUpperCase();
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('aria-hidden', 'true');
  
  const rect = document.createElementNS(SVG_NS, 'rect');
  rect.setAttribute('width', '16');
  rect.setAttribute('height', '16');
  rect.setAttribute('rx', '3');
  rect.setAttribute('fill', 'var(--pr-line)');
  svg.appendChild(rect);
  
  const text = document.createElementNS(SVG_NS, 'text');
  text.setAttribute('x', '8');
  text.setAttribute('y', '11.5');
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('font-family', 'var(--font-sans, sans-serif)');
  text.setAttribute('font-size', '10');
  text.setAttribute('font-weight', '600');
  text.setAttribute('fill', 'var(--pr-ink-2)');
  text.textContent = letter;
  svg.appendChild(text);
  
  return svg;
}

// ── Map "None Found" Badge ─────────────────────────────────────
function createNoneFoundBadge(ringR) {
  const g = document.createElementNS(SVG_NS, 'g');
  g.classList.add('pr-map-none-found-badge');
  g.setAttribute('data-ring-radius-none', String(ringR));
  const y = 280 - ringR;

  const rect = document.createElementNS(SVG_NS, 'rect');
  rect.setAttribute('x', '315');
  rect.setAttribute('y', String(y - 9));
  rect.setAttribute('width', '90');
  rect.setAttribute('height', '18');
  rect.setAttribute('rx', '4');
  rect.setAttribute('fill', 'var(--pr-paper)');
  g.appendChild(rect);

  const txt = document.createElementNS(SVG_NS, 'text');
  txt.setAttribute('x', '360');
  txt.setAttribute('y', String(y + 3.5));
  txt.setAttribute('text-anchor', 'middle');
  txt.setAttribute('font-family', 'var(--font-mono, monospace)');
  txt.setAttribute('font-size', '11');
  txt.setAttribute('fill', 'var(--pr-ink-3)');
  txt.textContent = "None found";
  g.appendChild(txt);

  return g;
}

function updateNoneFoundBadge(ringR, isNoneFound) {
  const gBadges = document.getElementById('pr-map-unavailable-badges');
  if (!gBadges) return;
  const existing = gBadges.querySelector(`[data-ring-radius-none="${ringR}"]`);
  if (isNoneFound) {
    if (!existing) {
      gBadges.appendChild(createNoneFoundBadge(ringR));
    }
  } else {
    if (existing) existing.remove();
  }
}

// ── Failed State Manager ────────────────────────────────────────
let rateLimitTimer = null;

function showFailedState(reason = 'network', details = '') {
  const failedPanel = document.getElementById('pr-failed-panel');
  const sheetBody = document.getElementById('pr-sheet-body');
  const titleEl = document.getElementById('pr-failed-title');
  const causeEl = document.getElementById('pr-failed-cause');
  const helpEl = document.getElementById('pr-failed-help');
  const retryBtn = document.getElementById('pr-failed-retry-btn');

  if (sheetBody) sheetBody.style.display = 'none';
  if (failedPanel) failedPanel.style.display = 'flex';

  if (rateLimitTimer) {
    clearInterval(rateLimitTimer);
    rateLimitTimer = null;
  }

  if (retryBtn) {
    retryBtn.disabled = false;
    retryBtn.textContent = 'Try again';
    retryBtn.style.opacity = '1';
    retryBtn.style.cursor = 'pointer';
    retryBtn.style.display = 'inline-flex';
  }

  const r = String(reason).toLowerCase();

  if (r.includes('valid') || r === 'validation') {
    if (titleEl) titleEl.textContent = 'Invalid domain';
    if (causeEl) causeEl.textContent = 'Enter a domain like example.com.';
    if (helpEl) helpEl.textContent = 'Check the spelling or format in the audit input above.';
    if (retryBtn) {
      retryBtn.textContent = 'Edit domain';
      retryBtn.onclick = () => {
        const inp = document.getElementById('pr-domain-input');
        if (inp) { inp.focus(); inp.select(); }
      };
    }
  } else if (r.includes('rate') || r.includes('429') || r === 'rate_limit') {
    if (titleEl) titleEl.textContent = 'Rate limit reached';
    if (causeEl) causeEl.textContent = "That's 10 audits in a minute. Try again shortly.";
    if (helpEl) helpEl.textContent = 'Please wait a moment before starting another audit.';
    triggerRateLimitCountdown(15);
  } else if (r.includes('stream') || r === 'stream_interrupted') {
    if (titleEl) titleEl.textContent = 'Audit stopped';
    if (causeEl) causeEl.textContent = 'The audit stopped before it finished. Nothing was saved. Try again.';
    if (helpEl) helpEl.textContent = 'You can run the audit again to scan the external attack surface.';
    if (retryBtn) retryBtn.onclick = handleFailedRetry;
  } else if (r.includes('server') && details) {
    if (titleEl) titleEl.textContent = 'Audit service error';
    if (causeEl) causeEl.textContent = details;
    if (helpEl) helpEl.textContent = 'You can retry now or try again in a few moments.';
    if (retryBtn) retryBtn.onclick = handleFailedRetry;
  } else {
    // Network / Offline fallback
    if (titleEl) titleEl.textContent = 'Connection failed';
    if (causeEl) causeEl.textContent = "We couldn't reach the audit service. Check your connection and try again.";
    if (helpEl) helpEl.textContent = 'Ensure you are connected to the network, then retry the audit.';
    if (retryBtn) retryBtn.onclick = handleFailedRetry;
  }
}

function hideFailedState() {
  const failedPanel = document.getElementById('pr-failed-panel');
  const sheetBody = document.getElementById('pr-sheet-body');
  if (failedPanel) failedPanel.style.display = 'none';
  if (sheetBody) sheetBody.style.display = 'block';
  if (rateLimitTimer) {
    clearInterval(rateLimitTimer);
    rateLimitTimer = null;
  }
}

function triggerRateLimitCountdown(seconds = 15) {
  const retryBtn = document.getElementById('pr-failed-retry-btn');
  if (!retryBtn) return;
  let remaining = seconds;
  retryBtn.disabled = true;
  retryBtn.textContent = `Try again (${remaining}s)`;
  retryBtn.style.opacity = '0.5';
  retryBtn.style.cursor = 'not-allowed';

  rateLimitTimer = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(rateLimitTimer);
      rateLimitTimer = null;
      retryBtn.disabled = false;
      retryBtn.textContent = 'Try again';
      retryBtn.style.opacity = '1';
      retryBtn.style.cursor = 'pointer';
    } else {
      retryBtn.textContent = `Try again (${remaining}s)`;
    }
  }, 1000);
}

function handleFailedRetry() {
  hideFailedState();
  if (state.domain) {
    run(state.domain);
  } else {
    const inp = document.getElementById('pr-domain-input');
    if (inp) inp.focus();
  }
}
window.showFailedState = showFailedState;
window.hideFailedState = hideFailedState;

// Safe LocalStorage access helper
function safeStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    return null;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    return false;
  }
}

function createInitialState() {
  return {
    phase: 'idle', // 'idle' | 'running' | 'complete' | 'failed'
    mode: 'sample', // 'sample' | 'live'
    domain: '',
    startedAt: null,
    checks: {
      domain:     { status: 'pending', data: null }, // from rdap
      tls:        { status: 'pending', data: null }, // from ssl
      email_auth: { status: 'pending', data: null },
      lookalikes: { status: 'pending', data: null },
      subdomains: { status: 'pending', data: null },
      surface:    { status: 'pending', data: null }
    },
    summary: null,
    ai: null,
    error: null, // { message: string, kind: 'validation'|'rate_limit'|'network'|'stream' }
    history: null // previous run for this domain (Part 4)
  };
}

let state = createInitialState();

function resetState(newProps = {}) {
  const fresh = createInitialState();
  for (const k of Object.keys(state)) {
    if (!(k in fresh)) {
      delete state[k];
    }
  }
  Object.assign(state, fresh, newProps);
  if (typeof resetPart4VisualState === 'function') resetPart4VisualState();
  return state;
}

// ── 2. History Storage Controller (Section 5) ───────────────────
const HISTORY_KEY = 'phishrecon:v2';
const phishReconHistory = {
  load() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      if (!raw) return { runs: {} };
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.runs === 'object') return parsed;
      return { runs: {} };
    } catch (e) {
      return { runs: {} };
    }
  },
  recordLiveRun(domain, score, posture) {
    if (score === null || score === undefined || posture === 'Not enough data') return;
    if (state.mode === 'sample' || (domain && domain.endsWith('.example'))) return;
    if (!domain || typeof score !== 'number') return;
    try {
      const data = this.load();
      if (!data.runs) data.runs = {};
      if (!Array.isArray(data.runs[domain])) data.runs[domain] = [];
      data.runs[domain].push({
        t: Date.now(),
        score: score,
        posture: posture || 'Unknown'
      });
      // Keep last 10 runs per domain
      if (data.runs[domain].length > 10) {
        data.runs[domain] = data.runs[domain].slice(-10);
      }
      // Keep at most 20 domains (prune oldest)
      const domains = Object.keys(data.runs);
      if (domains.length > 20) {
        domains.sort((a, b) => {
          const lastA = data.runs[a][data.runs[a].length - 1]?.t || 0;
          const lastB = data.runs[b][data.runs[b].length - 1]?.t || 0;
          return lastA - lastB;
        });
        while (Object.keys(data.runs).length > 20) {
          const oldest = domains.shift();
          delete data.runs[oldest];
        }
      }
      localStorage.setItem(HISTORY_KEY, JSON.stringify(data));
    } catch (e) {
      // Storage unavailable or blocked; fail silently
    }
  },
  getDomainHistory(domain) {
    if (!domain) return null;
    try {
      const data = this.load();
      const list = data.runs && data.runs[domain];
      if (Array.isArray(list) && list.length > 0) {
        const validRuns = list.filter(r => typeof r.score === 'number' && r.posture !== 'Not enough data');
      return validRuns.length > 0 ? validRuns[validRuns.length - 1] : null;
      }
      return null;
    } catch (e) {
      return null;
    }
  },
  getRecentDomains() {
    try {
      const data = this.load();
      const domains = Object.keys(data.runs || {});
      domains.sort((a, b) => {
        const lastA = data.runs[a][data.runs[a].length - 1]?.t || 0;
        const lastB = data.runs[b][data.runs[b].length - 1]?.t || 0;
        return lastB - lastA;
      });
      return domains.map(dom => {
        const validRuns = (data.runs[dom] || []).filter(r => typeof r.score === 'number' && r.posture !== 'Not enough data');
        const lastRun = validRuns[validRuns.length - 1];
        if (!lastRun) return null;
        return { domain: dom, score: lastRun.score, posture: lastRun.posture, t: lastRun.t };
      }).filter(Boolean).slice(0, 5);
    } catch (e) {
      return [];
    }
  }
};

// ── 3. Dispatcher (Section 2) ───────────────────────────────────
let hasAnnouncedLureClosing = false;

function triggerLureClosingOnce() {
  if (hasAnnouncedLureClosing) return;
  if (!state || state.phase !== 'complete' || state.instant) return;
  hasAnnouncedLureClosing = true;

  if (typeof window.lureShowRestrainedClosing !== 'function') return;

  const findings = typeof generateFindings === 'function' ? generateFindings(state) : [];
  const actionable = findings.filter(f => f.key !== 'checks_unavailable');
  const count = actionable.length;

  let line = '';
  if (count === 0) {
    line = "All clear across the perimeter. No active exposure risks detected.";
  } else if (count === 1) {
    line = "Found 1 thing worth your attention.";
  } else {
    line = `Found ${count} things worth your attention.`;
  }

  setTimeout(() => {
    if (typeof window.lureShowRestrainedClosing === 'function') {
      window.lureShowRestrainedClosing(line);
    }
  }, 700);
}

function dispatch(packet) {
  if (!packet || typeof packet !== 'object') return;

  // Pulse amber bulb on Lure mascot each time a new section streams in
  if (!state.instant && ['domain_ssl', 'email_auth', 'lookalikes', 'subdomains', 'exposed_surface', 'summary', 'ai'].includes(packet.stage)) {
    if (typeof window.lurePulseBulb === 'function') {
      window.lurePulseBulb();
    }
  }

  switch (packet.stage) {
    case 'domain_ssl': {
      const rdapStatus = packet.rdap && packet.rdap.status ? packet.rdap.status : 'unavailable';
      const sslStatus = packet.ssl && packet.ssl.status ? packet.ssl.status : 'unavailable';
      state.checks.domain = { status: rdapStatus, data: packet.rdap || null };
      state.checks.tls = { status: sslStatus, data: packet.ssl || null };
      break;
    }
    case 'email_auth': {
      const emailStatus = (packet.email_auth && packet.email_auth.status) || packet.status || 'unavailable';
      state.checks.email_auth = { status: emailStatus, data: packet.email_auth || packet };
      break;
    }
    case 'lookalikes': {
      const lookStatus = (packet.lookalikes && packet.lookalikes.status) || packet.status || 'unavailable';
      state.checks.lookalikes = { status: lookStatus, data: packet.lookalikes || packet };
      break;
    }
    case 'subdomains': {
      const subStatus = packet.status || 'unavailable';
      state.checks.subdomains = {
        status: subStatus,
        data: {
          count: typeof packet.count === 'number' ? packet.count : (packet.subdomains ? packet.subdomains.length : 0),
          subdomains: packet.subdomains || []
        }
      };
      break;
    }
    case 'exposed_surface': {
      const surfStatus = (packet.surface && packet.surface.status) || packet.status || 'unavailable';
      state.checks.surface = { status: surfStatus, data: packet.surface || packet };
      break;
    }
    case 'summary': {
      state.summary = packet;
      // Phase stays 'running' until the stream closes or the ai packet arrives
      if (state.mode === 'live' && typeof packet.exposure_score === 'number' && packet.posture !== 'Not enough data') {
        phishReconHistory.recordLiveRun(state.domain, packet.exposure_score, packet.posture);
      }
      break;
    }
    case 'ai': {
      state.ai = packet;
      state.phase = 'complete';
      window.isPhishReconScanning = false;
      triggerLureClosingOnce();
      break;
    }
    case 'error': {
      state.error = {
        message: packet.message || "The audit was interrupted. Please try again.",
        kind: 'stream'
      };
      window.isPhishReconScanning = false;
      if (state.summary) {
        state.phase = 'complete'; // keep summary, partial note in error
        triggerLureClosingOnce();
      } else {
        state.phase = 'failed';
      }
      break;
    }
    default:
      console.warn('[PhishRecon] Unknown packet stage:', packet);
  }

  render();
}

// ── 4. The Runner (Section 3) ───────────────────────────────────
let currentRunId = 0;
let currentAbortController = null;
let sampleTimers = [];

function abortInFlight() {
  currentRunId++;
  window.isPhishReconScanning = false;
  hasAnnouncedLureClosing = false;
  if (currentAbortController) {
    try {
      currentAbortController.abort();
    } catch (e) {}
    currentAbortController = null;
  }
  sampleTimers.forEach(t => clearTimeout(t));
  sampleTimers = [];
  if (typeof resetPart4VisualState === 'function') {
    resetPart4VisualState();
  }
  if (typeof resetSurfaceMapVisuals === 'function') {
    resetSurfaceMapVisuals();
  }
  if (state.phase === 'running') {
    state.phase = state.summary ? 'complete' : 'idle';
    render();
  }
}

function cleanDomainInput(raw) {
  if (typeof raw !== 'string') return '';
  let str = raw.trim();
  if (str.includes('@')) {
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

function normalizeDomain(raw) {
  return cleanDomainInput(raw);
}

const DOMAIN_VALIDATION_REGEX = /^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$/;

async function run(rawDomain, options = {}) {
  const isSample = Boolean(options.sample);
  const normalized = cleanDomainInput(rawDomain);

  // Client-side domain validation
  if (!DOMAIN_VALIDATION_REGEX.test(normalized)) {
    abortInFlight();
    resetState({
      domain: normalized || String(rawDomain || '').trim(),
      phase: 'failed',
      error: {
        message: "Enter a domain like example.com.",
        kind: 'validation'
      }
    });
    render();
    return;
  }

  // Abort any in-flight run and reset state cleanly
  abortInFlight();
  window.isPhishReconScanning = true;
  hasAnnouncedLureClosing = false;
  const runId = currentRunId;
  if (typeof autoOpenedAccordions !== 'undefined') {
    autoOpenedAccordions.clear();
    userManuallyToggledAccordions.clear();
    document.querySelectorAll('.pr-accordion').forEach(det => { det.open = false; });
  }

  resetState({
    domain: normalized,
    mode: isSample ? 'sample' : 'live',
    phase: 'running',
    startedAt: Date.now(),
    instant: Boolean(options.instant),
    history: phishReconHistory.getDomainHistory(normalized),
    checks: {
      domain:     { status: 'running', data: null },
      tls:        { status: 'running', data: null },
      email_auth: { status: 'running', data: null },
      lookalikes: { status: 'running', data: null },
      subdomains: { status: 'running', data: null },
      surface:    { status: 'running', data: null }
    }
  });

  // Keep input synchronized & update favicon
  const domainInput = document.getElementById('pr-domain-input');
  if (domainInput && domainInput.value !== normalized) {
    domainInput.value = normalized;
  }
  updateFavicon(normalized);

  render();

  if (isSample) {
    // ── Sample Mode: playback fixtures through dispatch() ──
    const fixtureEl = document.getElementById('pr-sample');
    let fixtures = null;
    try {
      fixtures = JSON.parse(fixtureEl ? fixtureEl.textContent : '{}');
    } catch (e) {
      console.warn('[PhishRecon] Failed to parse sample fixture JSON:', e);
    }

    const variantKey = options.variant || getSampleVariantFromUrl() || 'default';
    const packetList = (fixtures && fixtures[variantKey]) || (fixtures && fixtures.default) || [];

    if (options.instant) {
      // Instant display for returning visits in same session
      window.isPhishReconScanning = false;
      packetList.forEach(packet => dispatch(packet));
      if (state.summary) {
        state.phase = 'complete';
      }
      render();
      return;
    }

    const TIMINGS = {
      domain_ssl: 700,
      email_auth: 1100,
      lookalikes: 1500,
      subdomains: 2300,
      exposed_surface: 3000,
      summary: 3600,
      ai: 6000
    };

    packetList.forEach(packet => {
      const delay = TIMINGS[packet.stage] || 1000;
      const t = setTimeout(() => {
        if (runId !== currentRunId) return;
        dispatch(packet);
      }, delay);
      sampleTimers.push(t);
    });

    // Finalizer check if stream ends without AI
    const maxDelay = Math.max(...packetList.map(p => TIMINGS[p.stage] || 0), 6100);
    const endTimer = setTimeout(() => {
      if (runId !== currentRunId) return;
      window.isPhishReconScanning = false;
      if (state.summary && state.phase === 'running') {
        state.phase = 'complete';
        render();
        triggerLureClosingOnce();
      } else if (!state.summary && state.phase === 'running') {
        state.phase = 'failed';
        render();
      }
    }, maxDelay + 50);
    sampleTimers.push(endTimer);

  } else {
    // ── Live Mode: POST to /api/exposure-report ──
    currentAbortController = new AbortController();

    // Update URL without page reload
    try {
      history.replaceState(null, '', '?domain=' + encodeURIComponent(normalized));
    } catch (e) {}

    const formData = new FormData();
    formData.append('domain', normalized);

    try {
      const res = await fetch('/api/exposure-report', {
        method: 'POST',
        body: formData,
        signal: currentAbortController.signal
      });

      if (!res.ok) {
        if (runId !== currentRunId) return;
        window.isPhishReconScanning = false;
        let errMsg = "Server error (" + res.status + ")";
        let kind = 'network';
        try {
          const errData = await res.json();
          if (errData && errData.message) errMsg = errData.message;
        } catch (e) {}

        if (res.status === 429) {
          kind = 'rate_limit';
          errMsg = "That's 10 audits in a minute. Try again shortly.";
        }

        state.phase = 'failed';
        state.error = { message: errMsg, kind: kind };
        render();
        return;
      }

      // Read NDJSON stream chunk by chunk
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (runId !== currentRunId) {
          try { reader.cancel(); } catch (e) {}
          return;
        }
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep trailing incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const packet = JSON.parse(trimmed);
            dispatch(packet);
          } catch (jsonErr) {
            console.warn('[PhishRecon] malformed stream line:', trimmed, jsonErr);
          }
        }
      }

      // Check trailing buffer
      if (buffer.trim()) {
        try {
          const packet = JSON.parse(buffer.trim());
          dispatch(packet);
        } catch (jsonErr) {
          console.warn('[PhishRecon] malformed trailing stream line:', buffer, jsonErr);
        }
      }

      // Stream completed: check summary status
      if (runId !== currentRunId) return;
      window.isPhishReconScanning = false;
      if (state.summary) {
        state.phase = 'complete';
        triggerLureClosingOnce();
      } else {
        state.phase = 'failed';
      }
      render();

    } catch (err) {
      if (err.name === 'AbortError') return; // Handled cleanly on cancellation
      if (runId !== currentRunId) return;
      window.isPhishReconScanning = false;
      state.phase = 'failed';
      state.error = {
        message: err.message || "Network request failed. Check connection.",
        kind: 'network'
      };
      render();
    }
  }
}

function getSampleVariantFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const s = params.get('sample');
    if (s === 'partial' || s === 'low' || s === 'critical' || s === 'no_mail') return s;
    if (s !== null) return 'default';
  } catch (e) {}
  return null;
}

// ── Favicon & Globe Glyph Controller (Part 3) ───────────────────
function createGlobeSvg() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 20 20');
  svg.setAttribute('width', '18');
  svg.setAttribute('height', '18');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.6');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.classList.add('pr-fav-globe');

  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', '10');
  circle.setAttribute('cy', '10');
  circle.setAttribute('r', '7.5');
  svg.appendChild(circle);

  const path1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path1.setAttribute('d', 'M2.5 10h15');
  svg.appendChild(path1);

  const path2 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path2.setAttribute('d', 'M10 2.5a11 11 0 0 1 3.5 7.5 11 11 0 0 1-3.5 7.5 11 11 0 0 1-3.5-7.5A11 11 0 0 1 10 2.5z');
  svg.appendChild(path2);

  return svg;
}

function updateFavicon(domain) {
  const slot = document.getElementById('pr-fav-slot');
  if (!slot) return;
  const cleaned = cleanDomainInput(domain);
  if (!cleaned) {
    slot.replaceChildren(createGlobeSvg());
    return;
  }

  // Render stylized initial letter badge immediately (never an empty box)
  const letterSpan = document.createElement('span');
  letterSpan.className = 'pr-fav-letter';
  letterSpan.textContent = cleaned.charAt(0).toUpperCase();
  slot.replaceChildren(letterSpan);

  // Attempt to load audited domain favicon safely via proxy
  const img = document.createElement('img');
  img.className = 'pr-fav-img';
  img.alt = cleaned;
  img.referrerPolicy = 'no-referrer';
  img.onload = () => {
    slot.replaceChildren(img);
  };
  img.src = '/api/favicon?domain=' + encodeURIComponent(cleaned);
}

// ── Validation Helpers (Part 3) ─────────────────────────────────
function showValidationError(message) {
  const msgEl = document.getElementById('pr-validation-msg');
  const textEl = document.getElementById('pr-validation-text');
  if (!msgEl || !textEl) return;
  textEl.textContent = message || "Enter a domain like example.com.";
  msgEl.style.display = 'flex';
}

function clearValidationError() {
  const msgEl = document.getElementById('pr-validation-msg');
  if (msgEl) {
    msgEl.style.display = 'none';
  }
}

// ── Recent Audits Chips Renderer (Part 3) ───────────────────────
function renderRecentAudits() {
  const container = document.getElementById('pr-recent-chips');
  if (!container) return;

  const recentList = phishReconHistory.getRecentDomains();
  if (!recentList || recentList.length === 0) {
    const emptySpan = document.createElement('span');
    emptySpan.className = 'pr-recent-empty';
    emptySpan.textContent = "Audits use public data only. Audit results are not saved to an account; website data may be cached for up to 24 hours.";
    container.replaceChildren(emptySpan);
    return;
  }

  const chips = recentList.map(item => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'pr-recent-chip';

    let postureTone = 'low';
    const p = (item.posture || '').toLowerCase();
    if (p.includes('crit')) postureTone = 'critical';
    else if (p.includes('elev')) postureTone = 'elevated';
    else if (p.includes('mod')) postureTone = 'moderate';
    else if (p.includes('low')) postureTone = 'low';

    chip.title = `${item.domain}: ${item.score ?? '--'} (${item.posture || 'Unknown'})`;
    chip.setAttribute('aria-label', `Audit ${item.domain}, previous score ${item.score ?? '--'}, ${item.posture || 'Unknown'}`);

    const dot = document.createElement('span');
    dot.className = 'pr-recent-dot';
    dot.setAttribute('data-posture', postureTone);

    const domSpan = document.createElement('span');
    domSpan.className = 'pr-recent-domain';
    domSpan.textContent = item.domain;

    const scoreSpan = document.createElement('span');
    scoreSpan.className = 'pr-recent-score';
    scoreSpan.textContent = item.score !== null ? String(item.score) : '--';

    chip.appendChild(dot);
    chip.appendChild(domSpan);
    chip.appendChild(scoreSpan);

    chip.onclick = () => {
      const input = document.getElementById('pr-domain-input');
      if (input) input.value = item.domain;
      updateFavicon(item.domain);
      clearValidationError();
      run(item.domain, { sample: false });
    };

    return chip;
  });

  container.replaceChildren(...chips);
}

// ── Command Bar Action Handlers (Part 3) ────────────────────────
function handleFormSubmit() {
  const input = document.getElementById('pr-domain-input');
  if (!input) return;
  const raw = input.value;
  const cleaned = cleanDomainInput(raw);
  input.value = cleaned;
  updateFavicon(cleaned);

  if (!DOMAIN_VALIDATION_REGEX.test(cleaned)) {
    showValidationError("Enter a domain like example.com.");
    state.error = {
      message: "Enter a domain like example.com.",
      kind: 'validation'
    };
    state.phase = 'failed';
    render();
    return;
  }

  clearValidationError();
  run(cleaned, { sample: false });
}

function handleStopClick() {
  abortInFlight();
}

function handleReplaySampleClick() {
  const input = document.getElementById('pr-domain-input');
  if (input) input.value = 'acme.example';
  updateFavicon('acme.example');
  clearValidationError();
  run('acme.example', { sample: true, variant: 'default' });
}

// ── 5. Part 4 Presentation Helpers & Idempotent Renderer ──────

// SVG Shape Helpers (Distinguishable by geometry without color)
function createPostureIconSvg(postureTone) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  svg.setAttribute('fill', 'currentColor');
  svg.setAttribute('aria-hidden', 'true');

  if (postureTone === 'low') {
    // Circle
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', '8');
    circle.setAttribute('cy', '8');
    circle.setAttribute('r', '5.5');
    svg.appendChild(circle);
  } else if (postureTone === 'moderate') {
    // Diamond
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', '8,1.5 14.5,8 8,14.5 1.5,8');
    svg.appendChild(poly);
  } else if (postureTone === 'elevated') {
    // Triangle
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', '8,2 14.5,13.5 1.5,13.5');
    svg.appendChild(poly);
  } else if (postureTone === 'critical') {
    // Octagon
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', '5,1.5 11,1.5 14.5,5 14.5,11 11,14.5 5,14.5 1.5,11 1.5,5');
    svg.appendChild(poly);
  } else {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', '8');
    circle.setAttribute('cy', '8');
    circle.setAttribute('r', '4');
    svg.appendChild(circle);
  }
  return svg;
}

function createArrowSvg(dir) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 12 12');
  svg.setAttribute('width', '10');
  svg.setAttribute('height', '10');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  if (dir === 'up') {
    path.setAttribute('d', 'M6 9.5V2.5M2.5 6L6 2.5 9.5 6');
  } else {
    path.setAttribute('d', 'M6 2.5V9.5M2.5 6L6 9.5 9.5 6');
  }
  svg.appendChild(path);
  return svg;
}

function createCloseSvg() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');

  const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line1.setAttribute('x1', '3');
  line1.setAttribute('y1', '3');
  line1.setAttribute('x2', '13');
  line1.setAttribute('y2', '13');
  svg.appendChild(line1);

  const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line2.setAttribute('x1', '13');
  line2.setAttribute('y1', '3');
  line2.setAttribute('x2', '3');
  line2.setAttribute('y2', '13');
  svg.appendChild(line2);

  return svg;
}

function createInfoSvg() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');

  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', '8');
  circle.setAttribute('cy', '8');
  circle.setAttribute('r', '6.5');
  svg.appendChild(circle);

  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', '8');
  line.setAttribute('y1', '7');
  line.setAttribute('x2', '8');
  line.setAttribute('y2', '11');
  svg.appendChild(line);

  const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  dot.setAttribute('cx', '8');
  dot.setAttribute('cy', '5');
  dot.setAttribute('r', '0.6');
  dot.setAttribute('fill', 'currentColor');
  svg.appendChild(dot);

  return svg;
}

function formatAuditedDate(timestamp) {
  const d = new Date(timestamp || Date.now());
  const day = d.toLocaleDateString(undefined, { day: 'numeric' });
  const month = d.toLocaleDateString(undefined, { month: 'short' });
  const year = d.toLocaleDateString(undefined, { year: 'numeric' });
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
  return `${day} ${month} ${year}, ${time}`;
}

function getRunningChecksStatusText(checks) {
  if (!checks) return "Waiting on initial telemetry.";
  const names = [];
  if (checks.domain?.status === 'pending' || checks.domain?.status === 'running') {
    names.push('domain registration');
  }
  if (checks.tls?.status === 'pending' || checks.tls?.status === 'running') {
    names.push('certificate logs');
  }
  if (checks.lookalikes?.status === 'pending' || checks.lookalikes?.status === 'running') {
    names.push('look-alike domains');
  }
  if (checks.subdomains?.status === 'pending' || checks.subdomains?.status === 'running') {
    names.push('subdomain records');
  }
  if (checks.surface?.status === 'pending' || checks.surface?.status === 'running') {
    names.push('the company website');
  }

  if (names.length === 0) {
    return "Finalizing exposure assessment.";
  }
  if (names.length === 1) {
    return "Waiting on " + names[0] + ".";
  }
  if (names.length === 2) {
    return "Waiting on " + names[0] + " and " + names[1] + ".";
  }
  const last = names.pop();
  return "Waiting on " + names.join(', ') + ", and " + last + ".";
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Verdict line-by-line reveal choreography
function revealVerdictLines(containerEl, text, shouldAnimate = true) {
  if (!containerEl) return;
  containerEl.__verdictText = text;
  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Bind reflow-safe window resize listener (C2)
  if (!containerEl.__resizeBound) {
    containerEl.__resizeBound = true;
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (containerEl.__verdictText) {
          revealVerdictLines(containerEl, containerEl.__verdictText, false);
        }
      }, 120);
    });
  }

  const words = text.trim().split(/\s+/);
  const tempSpans = words.map((w, idx) => {
    const s = document.createElement('span');
    s.style.display = 'inline-block';
    s.style.wordBreak = 'normal';
    s.style.overflowWrap = 'break-word';
    s.textContent = w + (idx < words.length - 1 ? ' ' : '');
    return s;
  });
  containerEl.replaceChildren(...tempSpans);

  const lines = [];
  let curLine = [];
  let curTop = -1;
  tempSpans.forEach(s => {
    const top = s.offsetTop;
    if (curTop === -1 || Math.abs(top - curTop) < 6) {
      curLine.push(s.textContent);
      curTop = top;
    } else {
      lines.push(curLine.join(''));
      curLine = [s.textContent];
      curTop = top;
    }
  });
  if (curLine.length > 0) {
    lines.push(curLine.join(''));
  }

  const wraps = lines.map((lineText, idx) => {
    const wrap = document.createElement('span');
    wrap.className = 'pr-verdict-line-wrap';
    const inner = document.createElement('span');
    inner.className = 'pr-verdict-line-inner';
    inner.textContent = lineText;
    if (!shouldAnimate || isReducedMotion) {
      inner.style.transform = 'none';
      inner.style.transition = 'none';
    } else {
      inner.style.transform = 'translateY(100%)';
      inner.style.transition = 'transform 520ms var(--pr-ease)';
      inner.style.transitionDelay = `${idx * 90}ms`;
    }
    wrap.appendChild(inner);
    return wrap;
  });
  containerEl.replaceChildren(...wraps);

  if (shouldAnimate && !isReducedMotion) {
    void containerEl.offsetHeight;
    requestAnimationFrame(() => {
      wraps.forEach(w => {
        const inner = w.firstElementChild;
        if (inner) inner.style.transform = 'translateY(0)';
      });
    });
  }
}

// Track Segment Fills Controller
function updateSegmentFills(score, postureTone) {
  const s = Math.max(0, Math.min(100, score));
  let activeSeg = 0;
  if (s < 25) activeSeg = 0;
  else if (s < 50) activeSeg = 1;
  else if (s < 75) activeSeg = 2;
  else activeSeg = 3;

  const fills = [
    document.getElementById('pr-seg-fill-low'),
    document.getElementById('pr-seg-fill-moderate'),
    document.getElementById('pr-seg-fill-elevated'),
    document.getElementById('pr-seg-fill-critical')
  ];

  fills.forEach((fillEl, idx) => {
    if (!fillEl) return;
    if (idx < activeSeg) {
      // Segments below filled fully at 70% strength
      fillEl.style.width = '100%';
      fillEl.style.backgroundColor = 'color-mix(in srgb, var(--pr-tone) 70%, transparent)';
    } else if (idx === activeSeg) {
      // Filled to the score's exact position with full-strength posture color
      let pct = 0;
      if (idx === 0) pct = (s / 24) * 100;
      else if (idx === 1) pct = ((s - 25) / 24) * 100;
      else if (idx === 2) pct = ((s - 50) / 24) * 100;
      else pct = ((s - 75) / 25) * 100;
      pct = Math.max(0, Math.min(100, pct));
      fillEl.style.width = `${pct}%`;
      fillEl.style.backgroundColor = 'var(--pr-tone)';
    } else {
      // Segments above stay at 22%
      fillEl.style.width = '0%';
    }
  });
}

// Synchronized Exposure Line Animation (450ms hold, 900ms ease-in-out count-up & marker travel)
let exposureAnimId = null;
let exposureAnimTimeout = null;
let lastAnimatedScore = null;
let lastRevealedVerdict = null;
let lastAiVerdict = null;

function resetPart4VisualState() {
  if (exposureAnimId) {
    cancelAnimationFrame(exposureAnimId);
    exposureAnimId = null;
  }
  if (exposureAnimTimeout) {
    clearTimeout(exposureAnimTimeout);
    exposureAnimTimeout = null;
  }
  lastAnimatedScore = null;
  lastRevealedVerdict = null;
  lastAiVerdict = null;

  const aiEl = document.getElementById('pr-verdict-ai');
  if (aiEl) {
    aiEl.replaceChildren();
    aiEl.style.opacity = '0';
    aiEl.style.pointerEvents = 'none';
    aiEl.classList.remove('is-active');
  }
}

function triggerExposureAnimation(finalScore, postureTone, instant = false) {
  if (exposureAnimId) cancelAnimationFrame(exposureAnimId);
  if (exposureAnimTimeout) clearTimeout(exposureAnimTimeout);

  const markerEl = document.getElementById('pr-track-marker');
  const scoreEl = document.getElementById('pr-score-numeral');
  const chipEl = document.getElementById('pr-track-chip');
  const sheet = document.getElementById('pr-sheet');

  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (instant || isReducedMotion) {
    if (sheet) sheet.setAttribute('data-posture', postureTone);
    if (markerEl) {
      markerEl.style.display = 'block';
      markerEl.style.left = `${finalScore}%`;
    }
    if (scoreEl) scoreEl.textContent = String(finalScore);
    if (chipEl) chipEl.textContent = String(finalScore);
    updateSegmentFills(finalScore, postureTone);
    return;
  }

  // Pre-animation: marker visible at 0, numeral 0
  if (markerEl) {
    markerEl.style.display = 'block';
    markerEl.style.left = '0%';
  }
  if (scoreEl) scoreEl.textContent = '0';
  if (chipEl) chipEl.textContent = '0';
  updateSegmentFills(0, postureTone);

  // Hold 450ms deliberate beat
  exposureAnimTimeout = setTimeout(() => {
    // Set sheet's data-posture so top line and glow adopt posture tone in the same beat
    if (sheet) sheet.setAttribute('data-posture', postureTone);

    const startTime = performance.now();
    const duration = 900;

    function frame(now) {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const eased = easeInOutCubic(progress);
      const currentScore = Math.round(eased * finalScore);
      const currentPos = eased * finalScore;

      if (scoreEl) scoreEl.textContent = String(currentScore);
      if (chipEl) chipEl.textContent = String(currentScore);
      if (markerEl) markerEl.style.left = `${currentPos}%`;
      updateSegmentFills(currentPos, postureTone);

      if (progress < 1) {
        exposureAnimId = requestAnimationFrame(frame);
      } else {
        if (scoreEl) scoreEl.textContent = String(finalScore);
        if (chipEl) chipEl.textContent = String(finalScore);
        if (markerEl) markerEl.style.left = `${finalScore}%`;
        updateSegmentFills(finalScore, postureTone);
      }
    }

    exposureAnimId = requestAnimationFrame(frame);
  }, 450);
}

// Meta Favicon in Header Line (24px)
function updateMetaFavicon(domain) {
  const slot = document.getElementById('pr-meta-fav');
  if (!slot) return;
  const cleaned = cleanDomainInput(domain);
  if (!cleaned) {
    slot.replaceChildren(createGlobeSvg());
    return;
  }

  // Render stylized initial letter badge immediately (never an empty box)
  const letterSpan = document.createElement('span');
  letterSpan.className = 'pr-meta-fav-letter';
  letterSpan.textContent = cleaned.charAt(0).toUpperCase();
  slot.replaceChildren(letterSpan);

  // Attempt to load audited domain favicon safely via proxy
  const img = document.createElement('img');
  img.className = 'pr-meta-fav-img';
  img.alt = cleaned;
  img.referrerPolicy = 'no-referrer';
  img.onload = () => {
    slot.replaceChildren(img);
  };
  img.src = '/api/favicon?domain=' + encodeURIComponent(cleaned);
}

// Reusable Anchored Popover Controller (Used for "How this score works" & Part 7)
let activePopoverClose = null;

function showPopover({ anchorEl, title, rows, sentences, onClose }) {
  if (activePopoverClose) {
    activePopoverClose();
  }

  const popover = document.createElement('div');
  popover.className = 'pr-popover';
  popover.setAttribute('role', 'dialog');
  popover.setAttribute('aria-modal', 'false');
  popover.setAttribute('aria-label', title);

  const header = document.createElement('div');
  header.className = 'pr-popover-header';
  const titleSpan = document.createElement('span');
  titleSpan.textContent = title;
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'pr-popover-close';
  closeBtn.setAttribute('aria-label', 'Close popover');
  closeBtn.appendChild(createCloseSvg());
  header.appendChild(titleSpan);
  header.appendChild(closeBtn);
  popover.appendChild(header);

  if (rows && rows.length > 0) {
    const list = document.createElement('div');
    list.className = 'pr-popover-list';
    rows.forEach(r => {
      const row = document.createElement('div');
      row.className = 'pr-popover-row';
      const name = document.createElement('span');
      name.textContent = r.name;
      const pts = document.createElement('span');
      pts.className = 'pr-popover-row-pts';
      pts.textContent = 'up to ' + r.max + ' points';
      row.appendChild(name);
      row.appendChild(pts);
      list.appendChild(row);
    });
    popover.appendChild(list);
  }

  if (sentences && sentences.length > 0) {
    const desc = document.createElement('div');
    desc.className = 'pr-popover-desc';
    sentences.forEach(s => {
      const p = document.createElement('p');
      p.style.margin = '0';
      p.textContent = s;
      desc.appendChild(p);
    });
    popover.appendChild(desc);
  }

  document.body.appendChild(popover);

  function updatePosition() {
    if (!anchorEl || !document.body.contains(popover)) return;
    const rect = anchorEl.getBoundingClientRect();
    const popRect = popover.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    let top = rect.bottom + window.scrollY + 10;
    let left = rect.left + window.scrollX;

    // Prefer opening downwards; only flip upwards if space below is very tight and space above has room
    if (spaceBelow < (popRect.height + 20) && spaceAbove > (popRect.height + 24)) {
      top = rect.top + window.scrollY - popRect.height - 10;
    }
    const maxLeft = window.innerWidth - popRect.width - 16;
    if (left > maxLeft) {
      left = Math.max(16, maxLeft);
    }
    if (left < 16) left = 16;
    popover.style.top = `${Math.round(top)}px`;
    popover.style.left = `${Math.round(left)}px`;
  }

  updatePosition();

  const prevFocus = document.activeElement;
  closeBtn.focus();

  let isClosed = false;
  function close() {
    if (isClosed) return;
    isClosed = true;
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('pointerdown', handlePointerDown);
    window.removeEventListener('resize', updatePosition);
    window.removeEventListener('scroll', updatePosition);
    if (popover.parentNode) {
      popover.parentNode.removeChild(popover);
    }
    if (prevFocus && typeof prevFocus.focus === 'function') {
      prevFocus.focus();
    }
    if (onClose) onClose();
    if (activePopoverClose === close) {
      activePopoverClose = null;
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'Tab') {
      const focusables = popover.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function handlePointerDown(e) {
    if (!popover.contains(e.target) && !anchorEl.contains(e.target)) {
      close();
    }
  }

  closeBtn.onclick = close;
  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('pointerdown', handlePointerDown);
  window.addEventListener('resize', updatePosition);
  window.addEventListener('scroll', updatePosition);

  activePopoverClose = close;
  return close;
}

// Handlers for Score Explainer, Partial Retry & Analyst Note
function handleExplainScoreClick(btn) {
  showPopover({
    anchorEl: btn,
    title: "How this score works",
    rows: [
      { name: "Look-alike domains", max: EXPOSURE_WEIGHTS.lookalikes },
      { name: "Email authentication", max: EXPOSURE_WEIGHTS.email_auth },
      { name: "Domain age & registration", max: EXPOSURE_WEIGHTS.domain_age },
      { name: "TLS certificate", max: EXPOSURE_WEIGHTS.ssl },
      { name: "Discovered subdomains", max: EXPOSURE_WEIGHTS.subdomains },
      { name: "Public website surface", max: EXPOSURE_WEIGHTS.surface }
    ],
    sentences: [
      "Unassessed checks add 0 points to the score and are listed in the ledger.",
      "Scores before and after the email authentication update are not comparable (local history stores versioned records).",
      "A look-alike that resolves isn't proof of wrongdoing, only a reason to check who owns it."
    ]
  });
}

function handlePartialRetry() {
  if (state.mode === 'sample') {
    run(state.domain || 'acme.example', { sample: true, variant: 'partial' });
  } else {
    run(state.domain, { sample: false });
  }
}

function handleOpenAnalystNote() {
  const noteSection = document.getElementById('pr-analyst-note');
  if (noteSection) {
    noteSection.scrollIntoView({ behavior: 'smooth' });
  } else {
    showDemoToast("Analyst note (Part 7)");
  }
}

// ── Part 5: Hand-Built SVG Surface Map Controller ────────────────
const SVG_NS = 'http://www.w3.org/2000/svg';

function getDomainSeed(domain) {
  let h = 2166136261 >>> 0;
  const s = String(domain || 'acme.example').toLowerCase();
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 16777619) >>> 0;
  }
  return h;
}

const mapStateCache = {
  domain: null,
  lookalikesStatus: null,
  lookalikesDataKey: null,
  subdomainsStatus: null,
  subdomainsDataKey: null,
  surfaceStatus: null,
  surfaceDataKey: null,
  postureTone: null
};

function resetSurfaceMapVisuals() {
  mapStateCache.domain = null;
  mapStateCache.lookalikesStatus = null;
  mapStateCache.lookalikesDataKey = null;
  mapStateCache.subdomainsStatus = null;
  mapStateCache.subdomainsDataKey = null;
  mapStateCache.surfaceStatus = null;
  mapStateCache.surfaceDataKey = null;
  mapStateCache.postureTone = null;

  const gLook = document.getElementById('pr-map-group-lookalikes');
  const gSub = document.getElementById('pr-map-group-subdomains');
  const gSurf = document.getElementById('pr-map-group-surface');
  const gBadges = document.getElementById('pr-map-unavailable-badges');
  const legend = document.getElementById('pr-map-legend');
  const tooltip = document.getElementById('pr-map-tooltip');

  if (gLook) gLook.replaceChildren();
  if (gSub) gSub.replaceChildren();
  if (gSurf) gSurf.replaceChildren();
  if (gBadges) gBadges.replaceChildren();
  if (legend) legend.replaceChildren();
  if (tooltip) tooltip.style.display = 'none';

  ['pr-ring-surface', 'pr-ring-subdomains', 'pr-ring-lookalikes'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('is-unavailable');
  });

  const stop = document.getElementById('pr-map-tone-stop');
  if (stop) stop.style.stopColor = 'var(--pr-structure)';
}

let mapTooltipTimer = null;
let mapHideTimer = null;
let isHoveringTooltip = false;
let pinnedTooltipNode = null;
let activeHoverNode = null;

function initMapTooltipEvents() {
  const tooltip = document.getElementById('pr-map-tooltip');
  if (tooltip && !tooltip.__eventsBound) {
    tooltip.__eventsBound = true;
    tooltip.addEventListener('mouseenter', () => {
      isHoveringTooltip = true;
      if (mapHideTimer) {
        clearTimeout(mapHideTimer);
        mapHideTimer = null;
      }
    });
    tooltip.addEventListener('mouseleave', () => {
      isHoveringTooltip = false;
      if (pinnedTooltipNode) return;
      scheduleHideMapTooltip(200);
    });
  }
}

function showMapTooltip({ x, y, title, subtitle, action, onAction }) {
  const tooltip = document.getElementById('pr-map-tooltip');
  const frame = document.getElementById('pr-surface-map-frame');
  if (!tooltip || !frame) return;

  if (mapHideTimer) {
    clearTimeout(mapHideTimer);
    mapHideTimer = null;
  }

  initMapTooltipEvents();
  tooltip.replaceChildren();

  const titleRow = document.createElement('div');
  titleRow.className = 'pr-map-tooltip-title';
  titleRow.textContent = title;
  tooltip.appendChild(titleRow);

  if (subtitle) {
    const subRow = document.createElement('div');
    subRow.className = 'pr-map-tooltip-desc';
    subRow.textContent = subtitle;
    tooltip.appendChild(subRow);
  }

  if (action) {
    const actRow = document.createElement('div');
    actRow.className = 'pr-map-tooltip-action';
    actRow.textContent = action;
    actRow.style.cursor = 'pointer';
    if (onAction) {
      actRow.onclick = (e) => {
        e.stopPropagation();
        onAction();
      };
    }
    tooltip.appendChild(actRow);
  }

  const leftPct = (x / 720) * 100;
  const topPct = (y / 560) * 100;
  tooltip.style.left = `${leftPct}%`;
  tooltip.style.top = `${topPct}%`;
  tooltip.style.display = 'block';
  tooltip.setAttribute('aria-hidden', 'false');

  frame.classList.add('has-node-hover');
}

function scheduleHideMapTooltip(delay = 320) {
  if (mapHideTimer) clearTimeout(mapHideTimer);
  mapHideTimer = setTimeout(() => {
    if (!isHoveringTooltip && !pinnedTooltipNode) {
      hideMapTooltip();
    }
  }, delay);
}

function hideMapTooltip() {
  if (mapTooltipTimer) {
    clearTimeout(mapTooltipTimer);
    mapTooltipTimer = null;
  }
  if (mapHideTimer) {
    clearTimeout(mapHideTimer);
    mapHideTimer = null;
  }
  isHoveringTooltip = false;
  pinnedTooltipNode = null;
  activeHoverNode = null;

  const tooltip = document.getElementById('pr-map-tooltip');
  const frame = document.getElementById('pr-surface-map-frame');
  if (tooltip) {
    tooltip.style.display = 'none';
    tooltip.setAttribute('aria-hidden', 'true');
  }
  if (frame) {
    frame.classList.remove('has-node-hover');
  }
  document.querySelectorAll('.is-active-target').forEach(el => el.classList.remove('is-active-target'));
}

function attachNodeInteraction(targetEl, relatedEls, tooltipData, clickHandler) {
  initMapTooltipEvents();

  targetEl.addEventListener('mouseenter', () => {
    if (pinnedTooltipNode) return;
    activeHoverNode = targetEl;
    targetEl.classList.add('is-active-target');
    relatedEls.forEach(el => el.classList.add('is-active-target'));
    if (mapHideTimer) {
      clearTimeout(mapHideTimer);
      mapHideTimer = null;
    }
    if (mapTooltipTimer) clearTimeout(mapTooltipTimer);
    mapTooltipTimer = setTimeout(() => {
      showMapTooltip(tooltipData);
    }, 40);
  });

  targetEl.addEventListener('focus', () => {
    if (pinnedTooltipNode) return;
    activeHoverNode = targetEl;
    targetEl.classList.add('is-active-target');
    relatedEls.forEach(el => el.classList.add('is-active-target'));
    if (mapHideTimer) {
      clearTimeout(mapHideTimer);
      mapHideTimer = null;
    }
    showMapTooltip(tooltipData);
  });

  targetEl.addEventListener('mouseleave', () => {
    if (pinnedTooltipNode) return;
    targetEl.classList.remove('is-active-target');
    relatedEls.forEach(el => el.classList.remove('is-active-target'));
    scheduleHideMapTooltip(320); // 320ms safe travel window
  });

  targetEl.addEventListener('blur', () => {
    if (pinnedTooltipNode) return;
    targetEl.classList.remove('is-active-target');
    relatedEls.forEach(el => el.classList.remove('is-active-target'));
    scheduleHideMapTooltip(150);
  });

  targetEl.addEventListener('click', (e) => {
    e.stopPropagation();
    if (mapHideTimer) {
      clearTimeout(mapHideTimer);
      mapHideTimer = null;
    }
    if (pinnedTooltipNode === targetEl) {
      pinnedTooltipNode = null;
      hideMapTooltip();
      return;
    }
    document.querySelectorAll('.is-active-target').forEach(el => el.classList.remove('is-active-target'));
    pinnedTooltipNode = targetEl;
    activeHoverNode = targetEl;
    targetEl.classList.add('is-active-target');
    relatedEls.forEach(el => el.classList.add('is-active-target'));
    showMapTooltip(tooltipData);
  });

  targetEl.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      pinnedTooltipNode = null;
      hideMapTooltip();
    } else if (e.key === 'Enter' || e.key === ' ') {
      pinnedTooltipNode = targetEl;
      showMapTooltip(tooltipData);
      if (clickHandler) {
        e.preventDefault();
        clickHandler(e);
      }
    }
  });
}

// Click outside dismisses pinned tooltip
document.addEventListener('pointerdown', (e) => {
  const tooltip = document.getElementById('pr-map-tooltip');
  if (pinnedTooltipNode && tooltip) {
    if (!tooltip.contains(e.target) && !pinnedTooltipNode.contains(e.target)) {
      pinnedTooltipNode = null;
      hideMapTooltip();
    }
  }
});

// Global Escape dismisses pinned tooltip
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && pinnedTooltipNode) {
    pinnedTooltipNode = null;
    hideMapTooltip();
  }
});

function createUnavailableBadge(ringR) {
  const g = document.createElementNS(SVG_NS, 'g');
  g.classList.add('pr-map-unavailable-badge');
  g.setAttribute('data-ring-radius', String(ringR));
  const y = 280 - ringR;

  const rect = document.createElementNS(SVG_NS, 'rect');
  rect.setAttribute('x', '302');
  rect.setAttribute('y', String(y - 9));
  rect.setAttribute('width', '116');
  rect.setAttribute('height', '18');
  rect.setAttribute('rx', '4');
  rect.setAttribute('fill', 'var(--pr-paper)');
  g.appendChild(rect);

  const iconG = document.createElementNS(SVG_NS, 'g');
  iconG.setAttribute('transform', `translate(310, ${y - 6})`);
  const c = document.createElementNS(SVG_NS, 'circle');
  c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '5.5');
  c.setAttribute('fill', 'none'); c.setAttribute('stroke', 'var(--pr-ink-3)'); c.setAttribute('stroke-width', '1.2');
  const d = document.createElementNS(SVG_NS, 'circle');
  d.setAttribute('cx', '6'); d.setAttribute('cy', '4'); d.setAttribute('r', '0.6'); d.setAttribute('fill', 'var(--pr-ink-3)');
  const l = document.createElementNS(SVG_NS, 'line');
  l.setAttribute('x1', '6'); l.setAttribute('y1', '5.5'); l.setAttribute('x2', '6'); l.setAttribute('y2', '8.5');
  l.setAttribute('stroke', 'var(--pr-ink-3)'); l.setAttribute('stroke-width', '1.2');
  iconG.appendChild(c); iconG.appendChild(d); iconG.appendChild(l);
  g.appendChild(iconG);

  const txt = document.createElementNS(SVG_NS, 'text');
  txt.setAttribute('x', '327');
  txt.setAttribute('y', String(y + 3.5));
  txt.setAttribute('font-family', 'var(--font-mono, monospace)');
  txt.setAttribute('font-size', '11');
  txt.setAttribute('fill', 'var(--pr-ink-3)');
  txt.textContent = "Couldn't check";
  g.appendChild(txt);

  return g;
}

function updateUnavailableBadge(ringR, isUnavailable) {
  const gBadges = document.getElementById('pr-map-unavailable-badges');
  if (!gBadges) return;
  const existing = gBadges.querySelector(`[data-ring-radius="${ringR}"]`);
  if (isUnavailable) {
    if (!existing) {
      gBadges.appendChild(createUnavailableBadge(ringR));
    }
  } else {
    if (existing) existing.remove();
  }
}

function navigateToEvidenceRow(itemKey) {
  if (!itemKey) return;
  let target = null;
  try {
    target = document.querySelector(`[data-evidence-item="${CSS.escape(itemKey)}"]`);
  } catch (e) {
    target = document.querySelector(`[data-evidence-item="${itemKey}"]`);
  }
  if (!target) {
    target = document.getElementById(`pr-evidence-${itemKey}`) ||
             document.querySelector(`[data-check-section="${itemKey}"]`) ||
             document.getElementById('pr-evidence') ||
             document.getElementById('pr-top-grid');
  }
  if (target) {
    const parentDetails = target.closest('details.pr-accordion') || (target.tagName === 'DETAILS' ? target : null);
    if (parentDetails) {
      parentDetails.open = true;
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    target.style.transition = 'background-color 300ms ease, outline 300ms ease';
    target.style.backgroundColor = 'rgba(14, 165, 233, 0.12)';
    target.style.outline = '2px solid var(--pr-structure)';
    setTimeout(() => {
      target.style.backgroundColor = '';
      target.style.outline = '';
    }, 1500);
  }
}

function renderSurfaceMap(state) {

  // C1: Crop SVG margins on narrow mobile viewports (< 600px)
  const mapSvg = document.getElementById('pr-surface-map-svg');
  if (mapSvg && window.innerWidth <= 600) {
    mapSvg.setAttribute('viewBox', '75 10 570 540');
  } else if (mapSvg) {
    mapSvg.setAttribute('viewBox', '0 0 720 560');
  }

  const currentDomain = state.domain || 'acme.example';
  const seed = getDomainSeed(currentDomain);
  const seedAngleDeg = seed % 360;
  const seedRad = (seedAngleDeg * Math.PI) / 180;
  const isInstant = Boolean(state.instant);

  // 1. Center Disc (Domain & Favicon)
  if (mapStateCache.domain !== currentDomain) {
    mapStateCache.domain = currentDomain;
    const domTxt = document.getElementById('pr-map-center-domain');
    if (domTxt) domTxt.textContent = currentDomain;

    const favImg = document.getElementById('pr-map-center-fav');
    const fallbackTxt = document.getElementById('pr-map-center-letter');
    if (favImg && fallbackTxt) {
      const cleanDom = cleanDomainInput(currentDomain);
      const initial = cleanDom.charAt(0).toUpperCase();
      fallbackTxt.textContent = initial;

      const favUrl = '/api/favicon?domain=' + encodeURIComponent(cleanDom);
      favImg.setAttribute('href', favUrl);
      favImg.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', favUrl);
      favImg.style.display = 'block';
      fallbackTxt.style.display = 'none';

      favImg.onerror = () => {
        favImg.style.display = 'none';
        fallbackTxt.style.display = 'block';
      };
    }
  }

  // 2. Posture Gradient Halo Circle (Encoded tone)
  let postureTone = 'neutral';
  if (state.summary && state.summary.posture) {
    const p = state.summary.posture.toLowerCase();
    if (p.includes('crit')) postureTone = 'critical';
    else if (p.includes('elev')) postureTone = 'elevated';
    else if (p.includes('mod')) postureTone = 'moderate';
    else if (p.includes('low')) postureTone = 'low';
  }

  if (mapStateCache.postureTone !== postureTone) {
    mapStateCache.postureTone = postureTone;
    const stop = document.getElementById('pr-map-tone-stop');
    if (stop) {
      if (postureTone === 'critical') stop.style.stopColor = 'var(--pr-crit)';
      else if (postureTone === 'elevated') stop.style.stopColor = 'var(--pr-elevated)';
      else if (postureTone === 'moderate') stop.style.stopColor = 'var(--pr-mod)';
      else if (postureTone === 'low') stop.style.stopColor = 'var(--pr-low)';
      else stop.style.stopColor = 'var(--pr-structure)';
    }
  }

  // 3. Ring 3: Look-alikes (r=236)
  const lookStatus = state.checks.lookalikes?.status;
  const lookData = state.checks.lookalikes?.data;
  const lookDataKey = lookData ? JSON.stringify(lookData.details || []) : null;

  if (mapStateCache.lookalikesStatus !== lookStatus || mapStateCache.lookalikesDataKey !== lookDataKey) {
    mapStateCache.lookalikesStatus = lookStatus;
    mapStateCache.lookalikesDataKey = lookDataKey;

    const ring3 = document.getElementById('pr-ring-lookalikes');
    const groupLook = document.getElementById('pr-map-group-lookalikes');

    if (lookStatus === 'unavailable' || (state.summary && Array.isArray(state.summary.incomplete) && state.summary.incomplete.some(k => k.includes('look')))) {
      if (ring3) ring3.classList.add('is-unavailable');
      updateUnavailableBadge(236, true);
      if (groupLook) groupLook.replaceChildren();
    } else {
      if (ring3) ring3.classList.remove('is-unavailable');
      updateUnavailableBadge(236, false);

      if (groupLook && lookData && (lookStatus === 'ok' || lookData.details)) {
        groupLook.replaceChildren();
        const details = lookData.details || [];
        const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves);
        const nonResolving = details.filter(d => !(d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves));

        // Spread resolving diamonds evenly around 360 deg
        const K_res = resolving.length;
        const resAngles = resolving.map((_, i) => (seedAngleDeg + i * (360 / Math.max(1, K_res))) % 360);

        // Collision avoidance pass (push +10 deg up to 5 times)
        for (let pass = 0; pass < 5; pass++) {
          let collided = false;
          for (let i = 0; i < K_res; i++) {
            for (let j = i + 1; j < K_res; j++) {
              let diff = Math.abs(resAngles[i] - resAngles[j]);
              if (diff > 180) diff = 360 - diff;
              if (diff < 28) { // labels would touch or overlap
                resAngles[j] = (resAngles[j] + 10) % 360;
                collided = true;
              }
            }
          }
          if (!collided) break;
        }

        // Draw resolving candidates
        resolving.forEach((cand, idx) => {
          const thetaDeg = resAngles[idx];
          const thetaRad = (thetaDeg * Math.PI) / 180;
          const cos = Math.cos(thetaRad);
          const sin = Math.sin(thetaRad);
          const x = 360 + 236 * cos;
          const y = 280 + 236 * sin;
          const x0 = 360 + 44 * cos;
          const y0 = 280 + 44 * sin;

          if (cand.same_infrastructure) {
            // Hollow circle r=5 with generous 32px hit area
            const nodeWrap = document.createElementNS(SVG_NS, 'g');
            nodeWrap.classList.add('pr-map-interactive-node');
            nodeWrap.setAttribute('tabindex', '0');
            nodeWrap.setAttribute('role', 'img');
            nodeWrap.setAttribute('aria-label', `Look-alike ${cand.domain} points to your own servers`);

            const hitTarget = document.createElementNS(SVG_NS, 'circle');
            hitTarget.setAttribute('cx', String(x));
            hitTarget.setAttribute('cy', String(y));
            hitTarget.setAttribute('r', '16');
            hitTarget.setAttribute('fill', 'transparent');
            hitTarget.setAttribute('pointer-events', 'all');
            hitTarget.style.cursor = 'pointer';
            nodeWrap.appendChild(hitTarget);

            const circle = document.createElementNS(SVG_NS, 'circle');
            circle.setAttribute('cx', String(x));
            circle.setAttribute('cy', String(y));
            circle.setAttribute('r', '5');
            circle.setAttribute('fill', 'none');
            circle.setAttribute('stroke', 'var(--pr-low)');
            circle.setAttribute('stroke-width', '1.5');
            circle.classList.add('pr-map-node');
            circle.setAttribute('pointer-events', 'none');
            nodeWrap.appendChild(circle);

            attachNodeInteraction(nodeWrap, [], {
              x, y,
              title: cand.domain,
              subtitle: "Points to your own servers",
              action: "View in evidence",
              onAction: () => navigateToEvidenceRow(cand.domain)
            }, () => navigateToEvidenceRow(cand.domain));

            groupLook.appendChild(nodeWrap);
          } else {
            // Resolving on external infrastructure -> Red Diamond & Dashed Spoke with 32px hit area
            const spoke = document.createElementNS(SVG_NS, 'line');
            spoke.setAttribute('x1', String(x0));
            spoke.setAttribute('y1', String(y0));
            spoke.setAttribute('x2', String(x));
            spoke.setAttribute('y2', String(y));
            spoke.classList.add('pr-map-spoke-crit');
            groupLook.appendChild(spoke);

            const nodeWrap = document.createElementNS(SVG_NS, 'g');
            nodeWrap.classList.add('pr-map-interactive-node');
            nodeWrap.setAttribute('tabindex', '0');
            nodeWrap.setAttribute('role', 'img');
            nodeWrap.setAttribute('aria-label', `Resolving look-alike: ${cand.domain}, IP: ${cand.ip || 'unknown'}`);
            nodeWrap.setAttribute('data-tour', 'map-lookalike');

            const hitTarget = document.createElementNS(SVG_NS, 'circle');
            hitTarget.setAttribute('cx', String(x));
            hitTarget.setAttribute('cy', String(y));
            hitTarget.setAttribute('r', '16');
            hitTarget.setAttribute('fill', 'transparent');
            hitTarget.setAttribute('pointer-events', 'all');
            hitTarget.style.cursor = 'pointer';
            nodeWrap.appendChild(hitTarget);

            const diamond = document.createElementNS(SVG_NS, 'polygon');
            const pts = `${x},${y - 6.5} ${x + 6.5},${y} ${x},${y + 6.5} ${x - 6.5},${y}`;
            diamond.setAttribute('points', pts);
            diamond.setAttribute('fill', 'var(--pr-crit)');
            diamond.setAttribute('stroke', 'var(--pr-paper)');
            diamond.setAttribute('stroke-width', '2');
            diamond.classList.add('pr-map-node', 'pr-map-node-crit');
            diamond.setAttribute('pointer-events', 'none');
            nodeWrap.appendChild(diamond);

            // Always-Visible 2-line Label
            const isRight = cos >= 0;
            const lx = isRight ? x + 11 : x - 11;
            const anchor = isRight ? 'start' : 'end';

            const labelG = document.createElementNS(SVG_NS, 'g');
            labelG.classList.add('pr-map-lookalike-label');

            const textDom = document.createElementNS(SVG_NS, 'text');
            textDom.setAttribute('x', String(lx));
            textDom.setAttribute('y', String(y - 2));
            textDom.setAttribute('text-anchor', anchor);
            textDom.classList.add('pr-map-lookalike-label-dom');
            textDom.textContent = cand.domain;
            labelG.appendChild(textDom);

            if (cand.ip) {
              const textIp = document.createElementNS(SVG_NS, 'text');
              textIp.setAttribute('x', String(lx));
              textIp.setAttribute('y', String(y + 11));
              textIp.setAttribute('text-anchor', anchor);
              textIp.classList.add('pr-map-lookalike-label-ip');
              textIp.textContent = cand.ip;
              labelG.appendChild(textIp);
            }

            attachNodeInteraction(nodeWrap, [spoke, labelG], {
              x, y,
              title: cand.domain,
              subtitle: `${cand.ip || 'Resolves'} · Resolves. Ownership not verified.`,
              action: "View in evidence",
              onAction: () => navigateToEvidenceRow(cand.domain)
            }, () => navigateToEvidenceRow(cand.domain));

            groupLook.appendChild(nodeWrap);
            groupLook.appendChild(labelG);
          }
        });

        // Draw non-resolving ticks with generous hit target
        nonResolving.forEach((cand, j) => {
          const tDeg = (seedAngleDeg + (j + 0.5) * (360 / Math.max(1, nonResolving.length))) % 360;
          const tRad = (tDeg * Math.PI) / 180;
          const x = 360 + 236 * Math.cos(tRad);
          const y = 280 + 236 * Math.sin(tRad);

          const nodeWrap = document.createElementNS(SVG_NS, 'g');
          nodeWrap.classList.add('pr-map-interactive-node');
          nodeWrap.setAttribute('tabindex', '0');
          nodeWrap.setAttribute('role', 'img');

          const hitTarget = document.createElementNS(SVG_NS, 'circle');
          hitTarget.setAttribute('cx', String(x));
          hitTarget.setAttribute('cy', String(y));
          hitTarget.setAttribute('r', '14');
          hitTarget.setAttribute('fill', 'transparent');
          hitTarget.setAttribute('pointer-events', 'all');
          hitTarget.style.cursor = 'pointer';
          nodeWrap.appendChild(hitTarget);

          const tick = document.createElementNS(SVG_NS, 'circle');
          tick.setAttribute('cx', String(x));
          tick.setAttribute('cy', String(y));
          tick.setAttribute('r', '2.5');
          tick.setAttribute('fill', 'none');
          tick.setAttribute('stroke', 'var(--pr-ink-3)');
          tick.setAttribute('stroke-opacity', '0.6');
          tick.setAttribute('stroke-width', '1.2');
          tick.classList.add('pr-map-node');
          tick.setAttribute('pointer-events', 'none');

          const isUnknown = cand.state === 'unknown' || cand.status === 'unknown';
          if (isUnknown) {
            tick.setAttribute('stroke-dasharray', '1.5 2');
            nodeWrap.setAttribute('aria-label', `Look-alike ${cand.domain} couldn't be checked`);
            attachNodeInteraction(nodeWrap, [], {
              x, y,
              title: cand.domain,
              subtitle: "Couldn't be checked",
              action: "View in evidence",
              onAction: () => navigateToEvidenceRow(cand.domain)
            }, () => navigateToEvidenceRow(cand.domain));
          } else {
            nodeWrap.setAttribute('aria-label', `Look-alike checked and not found: ${cand.domain}`);
            attachNodeInteraction(nodeWrap, [], {
              x, y,
              title: cand.domain,
              subtitle: "Look-alike checked and not found (Does not resolve)",
              action: "View in evidence",
              onAction: () => navigateToEvidenceRow(cand.domain)
            }, () => navigateToEvidenceRow(cand.domain));
          }

          nodeWrap.appendChild(tick);
          groupLook.appendChild(nodeWrap);
        });
      }
    }
  }

  // 4. Ring 2: Subdomains (r=168)
  const subStatus = state.checks.subdomains?.status;
  const subData = state.checks.subdomains?.data;
  const subDataKey = subData ? JSON.stringify(subData.subdomains || []) : null;

  if (mapStateCache.subdomainsStatus !== subStatus || mapStateCache.subdomainsDataKey !== subDataKey) {
    mapStateCache.subdomainsStatus = subStatus;
    mapStateCache.subdomainsDataKey = subDataKey;

    const ring2 = document.getElementById('pr-ring-subdomains');
    const groupSub = document.getElementById('pr-map-group-subdomains');

    if (subStatus === 'unavailable' || (state.summary && Array.isArray(state.summary.incomplete) && state.summary.incomplete.some(k => k.includes('subdomain')))) {
      if (ring2) ring2.classList.add('is-unavailable');
      updateUnavailableBadge(168, true);
      if (groupSub) groupSub.replaceChildren();
    } else {
      if (ring2) ring2.classList.remove('is-unavailable');
      updateUnavailableBadge(168, false);

      if (groupSub && subData && (subStatus === 'ok' || subData.subdomains)) {
        groupSub.replaceChildren();
        const list = subData.subdomains || [];
        if (list.length === 0 && subStatus === 'ok') {
          updateNoneFoundBadge(168, true);
        } else {
          updateNoneFoundBadge(168, false);
        }
        const drawnCount = Math.min(25, list.length);

        for (let i = 0; i < drawnCount; i++) {
          const hostname = list[i];
          const angleRad = seedRad + (i * 137.508 * Math.PI) / 180;
          const cos = Math.cos(angleRad);
          const sin = Math.sin(angleRad);
          const x = 360 + 168 * cos;
          const y = 280 + 168 * sin;
          const x0 = 360 + 44 * cos;
          const y0 = 280 + 44 * sin;

          const isSpecial = /(?:staging|dev|test|internal|admin|vpn|sso|beta|old|backup)/i.test(hostname);
          const r = isSpecial ? 6 : 4.5;
          const shouldLabel = isSpecial || i < 6;
          const staggerDelay = isInstant ? 0 : Math.min(700, i * 28);

          // Spoke
          const spoke = document.createElementNS(SVG_NS, 'line');
          spoke.setAttribute('x1', String(x0));
          spoke.setAttribute('y1', String(y0));
          spoke.setAttribute('x2', String(x));
          spoke.setAttribute('y2', String(y));
          spoke.classList.add('pr-map-spoke');
          if (!isInstant) {
            spoke.style.strokeDasharray = '124';
            spoke.style.strokeDashoffset = '124';
            setTimeout(() => { spoke.style.strokeDashoffset = '0'; }, staggerDelay);
          }
          groupSub.appendChild(spoke);

          // Node Wrapper with generous 32px hit area
          const nodeWrap = document.createElementNS(SVG_NS, 'g');
          nodeWrap.classList.add('pr-map-interactive-node');
          nodeWrap.setAttribute('tabindex', '0');
          nodeWrap.setAttribute('role', 'img');
          nodeWrap.setAttribute('aria-label', `Subdomain ${hostname}${isSpecial ? ' (non-production system)' : ''}`);

          const hitTarget = document.createElementNS(SVG_NS, 'circle');
          hitTarget.setAttribute('cx', String(x));
          hitTarget.setAttribute('cy', String(y));
          hitTarget.setAttribute('r', '16');
          hitTarget.setAttribute('fill', 'transparent');
          hitTarget.setAttribute('pointer-events', 'all');
          hitTarget.style.cursor = 'pointer';
          nodeWrap.appendChild(hitTarget);

          // Visible glyph
          const node = document.createElementNS(SVG_NS, 'circle');
          node.setAttribute('cx', String(x));
          node.setAttribute('cy', String(y));
          node.setAttribute('r', String(r));
          node.classList.add('pr-map-node');
          node.setAttribute('pointer-events', 'none');
          node.setAttribute('fill', 'var(--pr-structure)');
          node.setAttribute('fill-opacity', '0.9');

          if (isSpecial) {
            node.setAttribute('stroke', 'var(--pr-mod)');
            node.setAttribute('stroke-width', '1.5');
            nodeWrap.setAttribute('data-tour', 'map-subdomain');
          }

          if (!isInstant) {
            node.style.transform = 'scale(0)';
            setTimeout(() => { node.style.transform = 'scale(1)'; }, staggerDelay);
          }
          nodeWrap.appendChild(node);

          let labelEl = null;
          if (shouldLabel) {
            const suffix = '.' + currentDomain;
            const shortName = hostname.endsWith(suffix) ? hostname.slice(0, -suffix.length) : hostname;
            const isRight = cos >= 0;
            const lx = isRight ? x + (isSpecial ? 9 : 8) : x - (isSpecial ? 9 : 8);
            const anchor = isRight ? 'start' : 'end';

            labelEl = document.createElementNS(SVG_NS, 'text');
            labelEl.setAttribute('x', String(lx));
            labelEl.setAttribute('y', String(y + 3.5));
            labelEl.setAttribute('text-anchor', anchor);
            labelEl.classList.add('pr-map-label', 'pr-map-subdomain-label');
            labelEl.textContent = shortName;
            groupSub.appendChild(labelEl);
          }

          const related = [spoke];
          if (labelEl) related.push(labelEl);

          attachNodeInteraction(nodeWrap, related, {
            x, y,
            title: hostname,
            subtitle: "Found in public certificate logs" + (isSpecial ? " · Non-production keyword" : ""),
            action: "View in evidence",
            onAction: () => navigateToEvidenceRow(hostname)
          }, () => navigateToEvidenceRow(hostname));

          groupSub.appendChild(nodeWrap);
        }
      }
    }
  }

  // 5. Ring 1: Surface (Emails & Profiles, r=92)
  const surfStatus = state.checks.surface?.status;
  const surfData = state.checks.surface?.data;
  const surfDataKey = surfData ? JSON.stringify({ e: surfData.emails, s: surfData.socials }) : null;

  if (mapStateCache.surfaceStatus !== surfStatus || mapStateCache.surfaceDataKey !== surfDataKey) {
    mapStateCache.surfaceStatus = surfStatus;
    mapStateCache.surfaceDataKey = surfDataKey;

    const ring1 = document.getElementById('pr-ring-surface');
    const groupSurf = document.getElementById('pr-map-group-surface');

    if (surfStatus === 'unavailable' || (state.summary && Array.isArray(state.summary.incomplete) && state.summary.incomplete.some(k => k.includes('surface')))) {
      if (ring1) ring1.classList.add('is-unavailable');
      updateUnavailableBadge(92, true);
      if (groupSurf) groupSurf.replaceChildren();
    } else {
      if (ring1) ring1.classList.remove('is-unavailable');
      updateUnavailableBadge(92, false);

      if (groupSurf && surfData && (surfStatus === 'ok' || surfData.emails || surfData.socials)) {
        groupSurf.replaceChildren();

        const items = [];
        (surfData.emails || []).forEach(em => {
          const val = typeof em === 'string' ? em : (em.email || em.address || (typeof em === 'object' ? Object.values(em)[0] : ''));
          if (val) items.push({ kind: 'email', val: String(val) });
        });

        if (surfData.socials && typeof surfData.socials === 'object') {
          Object.entries(surfData.socials).forEach(([k, v]) => {
            items.push({ kind: 'profile', platform: k, url: v });
          });
        }

        const M = items.length;
        items.forEach((item, idx) => {
          const angleDeg = M === 1 ? 90 : 20 + idx * (140 / Math.max(1, M - 1));
          const angleRad = (angleDeg * Math.PI) / 180;
          const x = 360 + 92 * Math.cos(angleRad);
          const y = 280 + 92 * Math.sin(angleRad);
          const staggerDelay = isInstant ? 0 : Math.min(500, idx * 28);

          if (item.kind === 'email') {
            const nodeWrap = document.createElementNS(SVG_NS, 'g');
            nodeWrap.classList.add('pr-map-interactive-node');
            nodeWrap.setAttribute('tabindex', '0');
            nodeWrap.setAttribute('role', 'img');
            nodeWrap.setAttribute('aria-label', `Public email on site: ${item.val}`);

            const hitTarget = document.createElementNS(SVG_NS, 'circle');
            hitTarget.setAttribute('cx', String(x));
            hitTarget.setAttribute('cy', String(y));
            hitTarget.setAttribute('r', '15');
            hitTarget.setAttribute('fill', 'transparent');
            hitTarget.setAttribute('pointer-events', 'all');
            hitTarget.style.cursor = 'pointer';
            nodeWrap.appendChild(hitTarget);

            const rect = document.createElementNS(SVG_NS, 'rect');
            rect.setAttribute('x', String(x - 3.5));
            rect.setAttribute('y', String(y - 3.5));
            rect.setAttribute('width', '7');
            rect.setAttribute('height', '7');
            rect.setAttribute('rx', '1.5');
            rect.setAttribute('fill', 'var(--pr-ink-2)');
            rect.classList.add('pr-map-node', 'pr-map-node-email');
            rect.setAttribute('pointer-events', 'none');

            if (!isInstant) {
              rect.style.transform = 'scale(0)';
              setTimeout(() => { rect.style.transform = 'scale(1)'; }, staggerDelay);
            }
            nodeWrap.appendChild(rect);

            attachNodeInteraction(nodeWrap, [], {
              x, y,
              title: item.val,
              subtitle: "Public employee email found on website",
              action: "Click to copy email",
              onAction: () => {
                navigator.clipboard.writeText(item.val).then(() => {
                  if (typeof showToast === 'function') showToast('Email copied');
                }).catch(() => {
                  if (typeof showToast === 'function') showToast('Email copied');
                });
              }
            }, () => {
              navigator.clipboard.writeText(item.val).then(() => {
                if (typeof showToast === 'function') showToast('Email copied');
              }).catch(() => {
                if (typeof showToast === 'function') showToast('Email copied');
              });
            });

            groupSurf.appendChild(nodeWrap);
          } else {
            const nodeWrap = document.createElementNS(SVG_NS, 'g');
            nodeWrap.classList.add('pr-map-interactive-node');
            nodeWrap.setAttribute('tabindex', '0');
            nodeWrap.setAttribute('role', 'img');
            nodeWrap.setAttribute('aria-label', `Public profile on site: ${item.platform}`);

            const hitTarget = document.createElementNS(SVG_NS, 'circle');
            hitTarget.setAttribute('cx', String(x));
            hitTarget.setAttribute('cy', String(y));
            hitTarget.setAttribute('r', '15');
            hitTarget.setAttribute('fill', 'transparent');
            hitTarget.setAttribute('pointer-events', 'all');
            hitTarget.style.cursor = 'pointer';
            nodeWrap.appendChild(hitTarget);

            const prof = document.createElementNS(SVG_NS, 'circle');
            prof.setAttribute('cx', String(x));
            prof.setAttribute('cy', String(y));
            prof.setAttribute('r', '4');
            prof.setAttribute('fill', 'none');
            prof.setAttribute('stroke', 'var(--pr-ink-2)');
            prof.setAttribute('stroke-width', '1.5');
            prof.classList.add('pr-map-node', 'pr-map-node-profile');
            prof.setAttribute('pointer-events', 'none');

            if (!isInstant) {
              prof.style.transform = 'scale(0)';
              setTimeout(() => { prof.style.transform = 'scale(1)'; }, staggerDelay);
            }
            nodeWrap.appendChild(prof);

            attachNodeInteraction(nodeWrap, [], {
              x, y,
              title: item.platform.charAt(0).toUpperCase() + item.platform.slice(1),
              subtitle: item.url || "Company social profile",
              action: "View profile URL",
              onAction: () => window.open(item.url, '_blank', 'noopener')
            }, () => {
              if (item.url) window.open(item.url, '_blank', 'noopener');
            });

            groupSurf.appendChild(nodeWrap);
          }
        });
      }
    }
  }

  // 6. Legend Row (Only shows entries that exist in current data)
  renderMapLegend(state);

  // 7. Stat Line (#pr-map-stat) & Map SVG summary aria-label
  const mapStat = document.getElementById('pr-map-stat');
  if (mapStat) {
    if (state.phase === 'running') {
      mapStat.textContent = 'Scanning external perimeter...';
      if (mapSvg) mapSvg.setAttribute('aria-label', 'Observed attack surface map: scanning perimeter');
    } else if (state.summary) {
      const subCount = subData?.count || (subData?.subdomains?.length) || 0;
      const lookCount = lookData?.resolving_count ?? (lookData?.details ? lookData.details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length : 0);
      const emailCount = surfData?.emails?.length || 0;
      const subPart = (subStatus === 'ok' || (subData && subData.subdomains && subData.subdomains.length > 0)) ? `${subCount} subdomains` : 'subdomains not assessed';
      const lookPart = (lookStatus === 'ok' || (lookData && lookData.details)) ? `${lookCount} resolving` : 'look-alikes not assessed';
      const surfPart = (surfStatus === 'ok') ? `${emailCount} emails` : 'website surface not assessed';
      mapStat.textContent = `${subPart} · ${lookPart} · ${surfPart}`;
      if (mapSvg) mapSvg.setAttribute('aria-label', `Observed attack surface map: ${subCount} subdomains, ${lookCount} resolving look-alikes, ${emailCount} emails`);
    } else {
      mapStat.textContent = 'Telemetry syncing';
      if (mapSvg) mapSvg.setAttribute('aria-label', 'Observed attack surface map');
    }
  }
}
window.renderSurfaceMap = renderSurfaceMap;
window.renderMap = renderSurfaceMap;

function createLegendGlyph(type) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 14 14');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  if (type === 'subdomain') {
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', '3.5');
    c.setAttribute('fill', 'var(--pr-structure)');
    svg.appendChild(c);
  } else if (type === 'special_subdomain') {
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', '4.5');
    c.setAttribute('fill', 'var(--pr-structure)');
    c.setAttribute('stroke', 'var(--pr-mod)');
    c.setAttribute('stroke-width', '1.5');
    svg.appendChild(c);
  } else if (type === 'lookalike_crit') {
    const p = document.createElementNS(SVG_NS, 'polygon');
    p.setAttribute('points', '7,2 12,7 7,12 2,7');
    p.setAttribute('fill', 'var(--pr-crit)');
    p.setAttribute('stroke', 'var(--pr-paper)');
    p.setAttribute('stroke-width', '1.2');
    svg.appendChild(p);
  } else if (type === 'lookalike_tick') {
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', '2.5');
    c.setAttribute('fill', 'none');
    c.setAttribute('stroke', 'var(--pr-ink-3)');
    c.setAttribute('stroke-width', '1.2');
    svg.appendChild(c);
  } else if (type === 'email') {
    const r = document.createElementNS(SVG_NS, 'rect');
    r.setAttribute('x', '3.5'); r.setAttribute('y', '3.5'); r.setAttribute('width', '7'); r.setAttribute('height', '7');
    r.setAttribute('rx', '1.5');
    r.setAttribute('fill', 'var(--pr-ink-2)');
    svg.appendChild(r);
  } else if (type === 'profile') {
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', '4');
    c.setAttribute('fill', 'none');
    c.setAttribute('stroke', 'var(--pr-ink-2)');
    c.setAttribute('stroke-width', '1.5');
    svg.appendChild(c);
  }
  return svg;
}

function renderMapLegend(state) {
  const legend = document.getElementById('pr-map-legend');
  if (!legend) return;

  const subData = state.checks.subdomains?.data;
  const lookData = state.checks.lookalikes?.data;
  const surfData = state.checks.surface?.data;

  const subStatus = state.checks.subdomains?.status;
  const lookStatus = state.checks.lookalikes?.status;
  const surfStatus = state.checks.surface?.status;

  const hasSubdomains = subData && subData.subdomains && subData.subdomains.length > 0;
  const hasSpecialSubdomains = hasSubdomains && subData.subdomains.some(s => /(?:staging|dev|test|internal|admin|vpn|sso|beta|old|backup)/i.test(s));
  const totalSubCount = subData?.count || (subData?.subdomains?.length || 0);
  const drawnSubCount = hasSubdomains ? Math.min(25, subData.subdomains.length) : 0;
  const extraSubdomains = totalSubCount > drawnSubCount ? totalSubCount - drawnSubCount : 0;

  const lookDetails = lookData?.details || [];
  const hasResolvingLook = lookDetails.some(d => (d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves) && !d.same_infrastructure);
  const hasNonResolvingLook = lookDetails.some(d => !(d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves));

  const hasEmails = surfData && surfData.emails && surfData.emails.length > 0;
  const hasProfiles = surfData && surfData.socials && Object.keys(surfData.socials).length > 0;

  const items = [];

  function createLegendItem(glyphType, labelText) {
    const item = document.createElement('div');
    item.className = 'pr-map-legend-item';
    item.setAttribute('role', 'listitem');
    const spanG = document.createElement('span');
    spanG.className = 'pr-map-legend-glyph';
    spanG.appendChild(createLegendGlyph(glyphType));
    const spanL = document.createElement('span');
    spanL.textContent = labelText;
    item.appendChild(spanG);
    item.appendChild(spanL);
    return item;
  }

  if (hasSubdomains && subStatus === 'ok') {
    items.push(createLegendItem('subdomain', 'Subdomain'));
  }

  if (hasSpecialSubdomains) {
    items.push(createLegendItem('special_subdomain', 'Ringed: names that often point to non-production systems'));
  }

  if (extraSubdomains > 0) {
    const chip = document.createElement('div');
    chip.className = 'pr-map-legend-item';
    chip.style.color = 'var(--pr-ink-3)';
    chip.textContent = `+ ${extraSubdomains} more not drawn`;
    items.push(chip);
  }

  if (hasResolvingLook) {
    items.push(createLegendItem('lookalike_crit', 'Look-alike that resolves'));
  }

  if (hasNonResolvingLook && lookStatus === 'ok') {
    items.push(createLegendItem('lookalike_tick', 'Look-alike checked and not found'));
  }

  if (hasEmails && surfStatus === 'ok') {
    items.push(createLegendItem('email', 'Email on the site'));
  }

  if (hasProfiles) {
    items.push(createLegendItem('profile', 'Profile on the site'));
  }

  legend.replaceChildren(...items);

  // Quiet line under map legend if DMARC or SPF is missing (domain-level finding)
  const noticeEl = document.getElementById('pr-map-email-notice');
  if (noticeEl) {
    const emailAuth = state.checks.email_auth?.data || state.email_auth;
    const emailStatus = state.checks.email_auth?.status || state.email_auth?.status;
    const isMissingDmarc = emailAuth && (emailAuth.dmarc?.status === 'missing' || !emailAuth.dmarc?.record);
    const isMissingSpf = emailAuth && (emailAuth.spf?.status === 'missing' || !emailAuth.spf?.record);

    if (emailStatus === 'ok' && (isMissingDmarc || isMissingSpf)) {
      noticeEl.replaceChildren();

      const glyphWrap = document.createElement('span');
      glyphWrap.className = 'pr-badge-shape-wrap is-exposed';
      glyphWrap.setAttribute('aria-hidden', 'true');
      const shape = document.createElement('span');
      shape.className = 'pr-badge-shape pr-shape-diamond';
      glyphWrap.appendChild(shape);

      const msgSpan = document.createElement('span');
      if (isMissingDmarc && isMissingSpf) {
        msgSpan.textContent = 'DMARC & SPF missing (domain-level email authentication not published)';
      } else if (isMissingDmarc) {
        msgSpan.textContent = 'DMARC missing (domain-level email authentication not published)';
      } else {
        msgSpan.textContent = 'SPF missing (domain-level email authorization not published)';
      }

      noticeEl.appendChild(glyphWrap);
      noticeEl.appendChild(msgSpan);
      noticeEl.style.display = 'inline-flex';
    } else {
      noticeEl.style.display = 'none';
      noticeEl.replaceChildren();
    }
  }
}

// ── 6. Idempotent Renderer ─────────────────────────────────────
function render() {
  if (state.phase === 'failed') {
    showFailedState(state.error?.reason || state.error?.kind || 'network', state.error?.message || state.error?.details);
    return;
  } else {
    hideFailedState();
  }

  // Handle interrupted state notice under verdict
  const interNotice = document.getElementById('pr-interrupted-notice');
  if (interNotice) {
    interNotice.style.display = (state.interrupted && state.summary) ? 'inline-flex' : 'none';
  }
  // 1. Update Debug Panel JSON
  const debugPre = document.getElementById('pr-debug-json');
  if (debugPre) {
    debugPre.textContent = JSON.stringify(state, null, 2);
  }

  // 2. Header Line (Favicon, Domain, Locale Date, Report ID)
  const metaDomainEl = document.getElementById('pr-target-domain');
  if (metaDomainEl && state.domain) {
    metaDomainEl.textContent = state.domain;
  }
  updateMetaFavicon(state.domain || 'acme.example');

  const metaDateEl = document.getElementById('pr-meta-date');
  if (metaDateEl) {
    metaDateEl.textContent = formatAuditedDate(state.startedAt);
  }

  const metaIdEl = document.getElementById('pr-meta-id');
  if (metaIdEl) {
    if (state.summary && state.summary.investigation_id) {
      metaIdEl.textContent = state.summary.investigation_id;
      metaIdEl.style.display = 'inline-block';
    } else {
      metaIdEl.style.display = 'none';
    }
  }

  // 3. The Verdict Sentence
  const heuristicEl = document.getElementById('pr-verdict-heuristic');
  const aiEl = document.getElementById('pr-verdict-ai');
  const checksStatusEl = document.getElementById('pr-checks-status');
  const provEl = document.getElementById('pr-verdict-provenance');

  if (state.summary && state.summary.executive_verdict) {
    if (checksStatusEl) {
      checksStatusEl.style.display = 'none';
    }
    if (heuristicEl) {
      heuristicEl.style.color = 'var(--pr-ink)';
      if (lastRevealedVerdict !== state.summary.executive_verdict) {
        revealVerdictLines(heuristicEl, state.summary.executive_verdict, true);
        lastRevealedVerdict = state.summary.executive_verdict;
      }
    }

    const hasAiVerdict = state.ai && state.ai.executive_verdict && (state.ai.path_used === 'heuristic+ai' || state.summary.path_used === 'heuristic+ai');

    if (hasAiVerdict) {
      if (aiEl) {
        if (lastAiVerdict !== state.ai.executive_verdict) {
          revealVerdictLines(aiEl, state.ai.executive_verdict, false);
          lastAiVerdict = state.ai.executive_verdict;
        }
        aiEl.style.opacity = '1';
        aiEl.style.pointerEvents = 'auto';
        aiEl.classList.add('is-active');
      }
      if (heuristicEl) {
        heuristicEl.style.opacity = '0';
        heuristicEl.style.pointerEvents = 'none';
        heuristicEl.classList.remove('is-active');
      }

      if (provEl) {
        provEl.style.display = 'flex';
        provEl.replaceChildren();
        provEl.appendChild(createInfoSvg());
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pr-verdict-provenance-btn';
        btn.id = 'pr-provenance-btn';
        btn.textContent = "Written by a language model from the checks below. It can be wrong.";
        btn.onclick = handleOpenAnalystNote;
        provEl.appendChild(btn);
      }
    } else {
      if (heuristicEl) {
        heuristicEl.style.opacity = '1';
        heuristicEl.style.pointerEvents = 'auto';
        heuristicEl.classList.add('is-active');
      }
      if (aiEl) {
        aiEl.style.opacity = '0';
        aiEl.style.pointerEvents = 'none';
        aiEl.classList.remove('is-active');
      }

      if (provEl) {
        provEl.style.display = 'flex';
        provEl.replaceChildren();
        provEl.appendChild(createInfoSvg());
        const span = document.createElement('span');
        span.id = 'pr-provenance-text';
        span.textContent = "Written from the checks below.";
        provEl.appendChild(span);
      }
    }
  } else if (state.phase === 'running') {
    if (heuristicEl) {
      heuristicEl.style.color = 'var(--pr-ink-3)';
      heuristicEl.style.opacity = '1';
      heuristicEl.style.pointerEvents = 'auto';
      heuristicEl.classList.add('is-active');
      const text = "Auditing " + (state.domain || "target") + ".";
      if (heuristicEl.textContent !== text) {
        revealVerdictLines(heuristicEl, text, false);
      }
    }
    if (aiEl) {
      aiEl.style.opacity = '0';
      aiEl.style.pointerEvents = 'none';
      aiEl.classList.remove('is-active');
    }
    if (checksStatusEl) {
      checksStatusEl.style.display = 'block';
      checksStatusEl.textContent = getRunningChecksStatusText(state.checks);
    }
    if (provEl) {
      provEl.style.display = 'none';
    }
  } else if (state.phase === 'failed') {
    if (heuristicEl) {
      heuristicEl.style.color = 'var(--pr-ink)';
      heuristicEl.style.opacity = '1';
      heuristicEl.style.pointerEvents = 'auto';
      heuristicEl.classList.add('is-active');
      const text = "Audit could not be completed.";
      revealVerdictLines(heuristicEl, text, false);
    }
    if (aiEl) {
      aiEl.style.opacity = '0';
      aiEl.style.pointerEvents = 'none';
    }
    if (checksStatusEl) {
      checksStatusEl.style.display = 'block';
      checksStatusEl.textContent = (state.error && state.error.message) || "Check domain and network connection.";
    }
    if (provEl) {
      provEl.style.display = 'none';
    }
  }

  // 4. The Exposure Line (Instrument)
  const postureIconEl = document.getElementById('pr-posture-icon');
  const postureWordEl = document.getElementById('pr-posture-word');
  const partialChipEl = document.getElementById('pr-chip-partial');
  const changeChipEl = document.getElementById('pr-chip-change');
  const partialNoticeEl = document.getElementById('pr-partial-notice');
  const partialNoticeText = document.getElementById('pr-partial-notice-text');

  const isNotEnoughData = Boolean(
    state.summary && (state.summary.posture === 'Not enough data' || state.summary.exposure_score === null)
  );

  if (isNotEnoughData) {
    // B1: Honest 'Not enough data' presentation: no score, no marker, neutral styling, retry action
    const scoreEl = document.getElementById('pr-score-numeral');
    if (scoreEl) scoreEl.textContent = '—';
    if (postureWordEl) postureWordEl.textContent = 'Not enough data';
    if (postureIconEl) postureIconEl.replaceChildren(createInfoSvg());

    const sheet = document.querySelector('.pr-sheet');
    if (sheet) sheet.setAttribute('data-posture', 'neutral');

    const trackBar = document.getElementById('pr-track');
    if (trackBar) {
      trackBar.setAttribute('aria-label', 'Exposure — not enough data to rate domain');
    }
    const marker = document.getElementById('pr-track-marker');
    if (marker) marker.style.display = 'none';

    // Neutralize segment fills
    ['pr-seg-fill-low', 'pr-seg-fill-moderate', 'pr-seg-fill-elevated', 'pr-seg-fill-critical'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.transform = 'scaleX(0)';
    });

    if (partialChipEl) partialChipEl.style.display = 'inline-flex';
    if (changeChipEl) changeChipEl.style.display = 'none';
    if (partialNoticeEl && partialNoticeText) {
      partialNoticeEl.style.display = 'flex';
      partialNoticeText.textContent = "We couldn't complete enough checks to rate this domain. Run it again in a minute.";
    }

    // Condensed bar update
    const cScore = document.getElementById('pr-condensed-score');
    if (cScore) cScore.textContent = '—';
    const cWord = document.getElementById('pr-condensed-posture-word');
    if (cWord) cWord.textContent = 'Not enough data';
    const cIcon = document.getElementById('pr-condensed-posture-icon');
    if (cIcon) cIcon.replaceChildren(createInfoSvg());

  } else if (state.summary && typeof state.summary.exposure_score === 'number') {
    const score = state.summary.exposure_score;
    const postureStr = state.summary.posture || 'Assessment complete';
    
    let postureTone = 'low';
    const p = postureStr.toLowerCase();
    if (p.includes('crit')) postureTone = 'critical';
    else if (p.includes('elev')) postureTone = 'elevated';
    else if (p.includes('mod')) postureTone = 'moderate';
    else if (p.includes('low')) postureTone = 'low';

    if (postureIconEl) {
      postureIconEl.replaceChildren(createPostureIconSvg(postureTone));
    }
    if (postureWordEl) {
      postureWordEl.textContent = postureStr;
    }
    const trackBar = document.getElementById('pr-track');
    if (trackBar) {
      trackBar.setAttribute('role', 'img');
      trackBar.setAttribute('aria-label', `Exposure ${score} out of 100, ${postureStr}. Lower is better.`);
    }

    if (lastAnimatedScore !== score) {
      lastAnimatedScore = score;
      triggerExposureAnimation(score, postureTone, Boolean(state.instant));
    }

    const isIncomplete = Array.isArray(state.summary.incomplete) && state.summary.incomplete.length > 0;
    if (isIncomplete) {
      if (partialChipEl) partialChipEl.style.display = 'inline-flex';
      if (partialNoticeEl && partialNoticeText) {
        partialNoticeEl.style.display = 'flex';
        const friendly = {
          domain_ssl: 'certificate and registration',
          lookalikes: 'look-alike domains',
          subdomains: 'subdomains',
          exposed_surface: 'company website',
          surface: 'company website',
          tls: 'certificate'
        };
        const missingNames = state.summary.incomplete.map(k => friendly[k] || k).join(', ');
        partialNoticeText.textContent = `Partial score. Not assessed: ${missingNames}. Run it again in a minute.`;
      }
    } else {
      if (partialChipEl) partialChipEl.style.display = 'none';
      if (partialNoticeEl) partialNoticeEl.style.display = 'none';
    }

    if (state.mode === 'live' && state.history && typeof state.history.score === 'number') {
      const prevScore = state.history.score;
      const delta = score - prevScore;
      const d = new Date(state.history.t);
      const shortDate = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

      if (changeChipEl) {
        changeChipEl.style.display = 'inline-flex';
        changeChipEl.replaceChildren();

        if (delta > 0) {
          changeChipEl.setAttribute('data-change', 'up');
          changeChipEl.appendChild(createArrowSvg('up'));
          changeChipEl.appendChild(document.createTextNode(`Up ${delta} since ${shortDate}`));
        } else if (delta < 0) {
          changeChipEl.setAttribute('data-change', 'down');
          changeChipEl.appendChild(createArrowSvg('down'));
          changeChipEl.appendChild(document.createTextNode(`Down ${Math.abs(delta)} since ${shortDate}`));
        } else {
          changeChipEl.setAttribute('data-change', 'same');
          changeChipEl.appendChild(document.createTextNode(`No change since ${shortDate}`));
        }
      }
    } else {
      if (changeChipEl) changeChipEl.style.display = 'none';
    }

  } else {
    const scoreNumEl = document.getElementById('pr-score-numeral');
    if (scoreNumEl) scoreNumEl.textContent = '—';
    const markerEl = document.getElementById('pr-track-marker');
    if (markerEl) markerEl.style.display = 'none';
    if (postureWordEl) postureWordEl.textContent = state.phase === 'running' ? 'Assessing' : 'Pending';
    if (postureIconEl) postureIconEl.replaceChildren();
    if (partialChipEl) partialChipEl.style.display = 'none';
    if (changeChipEl) changeChipEl.style.display = 'none';
    if (partialNoticeEl) partialNoticeEl.style.display = 'none';
    updateSegmentFills(0, 'none');
  }

  // 5. Surface Map Telemetry Status (Part 5 Placeholder)
  const mapStat = document.getElementById('pr-map-stat');
  if (mapStat) {
    if (state.phase === 'running') {
      mapStat.textContent = 'Scanning external perimeter...';
    } else if (state.summary) {
      mapStat.textContent = 'Attack surface indexed';
    } else {
      mapStat.textContent = 'Telemetry syncing';
    }
  }

  // 6. Notice Bar (Part 3)
  const noticeBar = document.getElementById('pr-notice-bar');
  if (noticeBar) {
    noticeBar.style.display = (state.mode === 'sample') ? 'flex' : 'none';
  }

  // 7. Indeterminate Progress Line (Part 3)
  const progressLine = document.getElementById('pr-progress-line');
  if (progressLine) {
    if (state.phase === 'running') {
      progressLine.classList.add('is-active');
    } else {
      progressLine.classList.remove('is-active');
    }
  }

  // 8. Command Bar Buttons & Controls Synchronization (Part 3)
  const auditBtn = document.getElementById('pr-audit-btn');
  const stopBtn = document.getElementById('pr-stop-btn');
  const isRunning = state.phase === 'running';

  if (auditBtn) {
    if (isRunning) {
      auditBtn.disabled = true;
      auditBtn.textContent = 'Auditing';
    } else {
      auditBtn.disabled = false;
      auditBtn.textContent = 'Audit domain';
    }
  }

  if (stopBtn) {
    stopBtn.style.display = isRunning ? 'inline-flex' : 'none';
  }

  // 9. Validation Message Synchronization (Part 3)
  if (state.error && state.error.kind === 'validation') {
    showValidationError(state.error.message);
  } else if (!state.error || state.error.kind !== 'validation') {
    clearValidationError();
  }

  // 10. "See a sample" Button Visibility (Part 3)
  const seeSampleBtn = document.getElementById('pr-see-sample-btn');
  if (seeSampleBtn) {
    const isSampleCurrent = state.mode === 'sample' && state.domain === 'acme.example';
    seeSampleBtn.style.display = isSampleCurrent ? 'none' : 'inline-flex';
  }

  // 11. Recent Audits Chips (Part 3)
  renderRecentAudits();

  // 12. Surface Map Instrument (Part 5)
  renderSurfaceMap(state);

  // 13. Start Here Section (Part 6)
  renderStartHere(state);

  // 14. Checks Ledger Section (Part 6)
  renderChecksLedger(state);

  // 15. Evidence Accordions & Analyst Note (Part 7)
  renderEvidenceSection(state);
  renderAnalystNote(state);

  // 16. Condensing Header & Actions (Part 8)
  renderCondensedHeader(state);
  renderMetaActions(state);
}

// ════════════════════════════════════════════════════════════════
// PART 6: START HERE & CHECKS LEDGER ENGINE
// ════════════════════════════════════════════════════════════════

let isFindingsExpanded = false;
let renderedFindingKeys = new Set();

function createSeverityMarkerSvg(severity) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 12 12');
  svg.setAttribute('width', '12');
  svg.setAttribute('height', '12');
  svg.setAttribute('aria-hidden', 'true');
  if (severity === 'Fix now') {
    const poly = document.createElementNS(SVG_NS, 'polygon');
    poly.setAttribute('points', '6,1 11,11 1,11');
    poly.setAttribute('fill', 'var(--pr-crit)');
    svg.appendChild(poly);
  } else if (severity === 'Worth a look') {
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5');
    c.setAttribute('fill', 'var(--pr-mod)');
    svg.appendChild(c);
  } else { // 'For awareness'
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5');
    c.setAttribute('fill', 'none');
    c.setAttribute('stroke', 'var(--pr-ink-3)');
    c.setAttribute('stroke-width', '1.8');
    svg.appendChild(c);
  }
  return svg;
}

function createCalmCheckSvg() {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('width', '16');
  svg.setAttribute('height', '16');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'var(--pr-low)');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const c = document.createElementNS(SVG_NS, 'circle');
  c.setAttribute('cx', '8'); c.setAttribute('cy', '8'); c.setAttribute('r', '7');
  const p = document.createElementNS(SVG_NS, 'polyline');
  p.setAttribute('points', '5 8 7.5 10.5 11 5.5');
  svg.appendChild(c);
  svg.appendChild(p);
  return svg;
}

function generateFindings(state) {
  const findings = [];
  const domain = state.domain || 'acme.example';

  const rdap = state.checks?.domain?.data || state.rdap;
  const rdapStatus = state.checks?.domain?.status || state.rdap?.status;

  const ssl = state.checks?.tls?.data || state.ssl;
  const sslStatus = state.checks?.tls?.status || state.ssl?.status;

  const lookalikes = state.checks?.lookalikes?.data || state.lookalikes;
  const lookStatus = state.checks?.lookalikes?.status || state.lookalikes?.status;

  const subdomains = state.checks?.subdomains?.data || state.subdomains;
  const subStatus = state.checks?.subdomains?.status || state.subdomains?.status;

  const surface = state.checks?.surface?.data || state.surface;
  const surfStatus = state.checks?.surface?.status || state.surface?.status;

  const emailAuth = state.checks?.email_auth?.data || state.email_auth;
  const emailStatus = state.checks?.email_auth?.status || state.email_auth?.status;

  // Rule 0: Email Authentication (missing DMARC/SPF -> Fix now; p=none or softfail or >10 lookups -> Worth a look)
  if (emailAuth && (emailStatus === 'ok' || emailAuth.dmarc || emailAuth.spf)) {
    const isMissingDmarc = emailAuth.dmarc?.status === 'missing' || !emailAuth.dmarc?.record;
    const isMissingSpf = emailAuth.spf?.status === 'missing' || !emailAuth.spf?.record;
    const isOpenSpf = emailAuth.spf?.status === 'open';

    if (isMissingDmarc || isMissingSpf || isOpenSpf) {
      let nextStep = `Publish an SPF record (TXT on ${domain}) and a DMARC policy (TXT on _dmarc.${domain}) with p=quarantine or p=reject.`;
      if (!isMissingDmarc && (isMissingSpf || isOpenSpf)) {
        nextStep = `Publish a valid SPF record (TXT on ${domain}) specifying authorized mail servers and ending in -all.`;
      } else if (!isMissingSpf && !isOpenSpf && isMissingDmarc) {
        nextStep = `Publish a DMARC policy record (TXT on _dmarc.${domain}) with at least p=quarantine or p=reject.`;
      }

      findings.push({
        key: 'email_auth_missing',
        ruleOrder: 0.5,
        severity: 'Fix now',
        severityRank: 1,
        title: `Anyone can send email that looks like it comes from ${domain}`,
        why: "Without an SPF record and DMARC enforcement policy, mail receivers cannot verify if messages claiming to come from your domain are authentic.",
        nextStep: nextStep
      });
    } else if (emailAuth.dmarc?.status === 'none') {
      findings.push({
        key: 'dmarc_monitoring_only',
        ruleOrder: 2.5,
        severity: 'Worth a look',
        severityRank: 2,
        title: "DMARC is monitoring only; spoofed mail is still delivered",
        why: "A policy of p=none instructs mail receivers to accept unauthorized messages claiming to come from your domain and only send reporting telemetry.",
        nextStep: `Review incoming DMARC reports (rua) to confirm all legitimate senders are aligned, then advance the policy to p=quarantine or p=reject.`
      });
    }

    if (emailAuth.spf?.status === 'lookup_limit_exceeded') {
      findings.push({
        key: 'spf_lookup_limit',
        ruleOrder: 2.6,
        severity: 'Worth a look',
        severityRank: 2,
        title: `SPF record exceeds the 10 DNS lookup limit (${emailAuth.spf.lookups || 11} lookups)`,
        why: "RFC 7208 limits SPF evaluations to 10 DNS queries. When exceeded, receivers evaluate SPF as a PermError and authentication fails.",
        nextStep: "Flatten your SPF include chain or replace DNS mechanisms with direct ip4/ip6 address blocks."
      });
    } else if (emailAuth.spf?.status === 'softfail' && !isMissingDmarc && emailAuth.dmarc?.status !== 'none') {
      findings.push({
        key: 'spf_softfail',
        ruleOrder: 2.7,
        severity: 'Worth a look',
        severityRank: 2,
        title: "SPF record is configured with a soft fail (~all)",
        why: "Soft fail instructs receivers to accept mail from unlisted IP addresses while tagging it as suspicious, rather than rejecting it outright.",
        nextStep: "Once all outbound senders are verified, switch the SPF record to -all (strict fail) to reject unauthorized senders."
      });
    }
  }

  // Rule 1: TLS (ssl.status ok and valid false -> Fix now)
  if (ssl && (sslStatus === 'ok' || ssl.valid !== undefined) && ssl.valid === false) {
    findings.push({
      key: 'tls_invalid',
      ruleOrder: 1,
      severity: 'Fix now',
      severityRank: 1,
      title: `The certificate on ${domain} isn't valid`,
      why: "Visitors see a browser warning, and attackers can imitate a site that already looks broken.",
      nextStep: "Renew or replace the certificate and confirm the server answers on port 443."
    });
  }

  // Rule 2: Look-alikes (live_count >= 1 -> Fix now if live_count >= 3 else Worth a look)
  if (lookalikes && (lookStatus === 'ok' || lookalikes.details || lookalikes.live_count !== undefined)) {
    const details = Array.isArray(lookalikes.details) ? lookalikes.details : [];
    const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves);
    const liveCount = Math.max(resolving.length, lookalikes.live_count || 0);

    if (liveCount >= 1) {
      const namedList = resolving.slice(0, 2).map(d => d.domain);
      const namedStr = namedList.length > 0 ? ` (${namedList.join(', ')})` : '';
      const isPlural = liveCount !== 1;
      const isCrit = liveCount >= 3;

      findings.push({
        key: 'lookalikes_resolving',
        ruleOrder: 2,
        severity: isCrit ? 'Fix now' : 'Worth a look',
        severityRank: isCrit ? 1 : 2,
        title: `${liveCount} look-alike domain${isPlural ? 's' : ''} resolve${isPlural ? '' : 's'}${namedStr}`,
        why: "Anyone can point a similar name at a phishing page. Resolving doesn't prove that, but it's the first thing to rule out.",
        nextStep: "Check who owns each one in RDAP. Register the ones you can, and report any that host a login page."
      });
    }
  }

  // Rule 3: Domain age (rdap ok and domain_age_days < 180 -> Worth a look)
  if (rdap && (rdapStatus === 'ok' || rdap.domain_age_days !== undefined || rdap.days !== undefined)) {
    const days = rdap.domain_age_days ?? rdap.days;
    if (typeof days === 'number' && days < 180) {
      findings.push({
        key: 'domain_age_young',
        ruleOrder: 3,
        severity: 'Worth a look',
        severityRank: 2,
        title: "This domain is under six months old",
        why: "New domains are filtered more aggressively by mail providers and trusted less by visitors.",
        nextStep: "Make sure SPF, DKIM and DMARC are set up before sending campaigns."
      });
    }
  }

  // Rule 4: Non-production names (any subdomain matching ringed-name rule -> Worth a look)
  if (subdomains && (subStatus === 'ok' || subdomains.subdomains)) {
    const subs = Array.isArray(subdomains.subdomains) ? subdomains.subdomains : [];
    const ringedKeywords = [
      'staging', 'dev', 'test', 'uat', 'admin', 'vpn', 'internal',
      'corp', 'beta', 'sandbox', 'demo', 'qa', 'lab', 'bastion',
      'dev-api', 'db-prod', 'jira', 'gitlab', 'k8s', 'status', 'sso', 'billing'
    ];
    
    const nonProd = subs.filter(s => {
      const parts = s.split('.');
      const subLabel = parts[0].toLowerCase();
      return ringedKeywords.some(kw => subLabel === kw || subLabel.startsWith(kw + '-') || subLabel.endsWith('-' + kw) || subLabel.includes(kw));
    });

    if (nonProd.length >= 1) {
      const namedList = nonProd.slice(0, 2);
      const namedStr = ` (${namedList.join(', ')})`;
      const isPlural = nonProd.length !== 1;

      findings.push({
        key: 'subdomains_nonprod',
        ruleOrder: 4,
        severity: 'Worth a look',
        severityRank: 2,
        title: `${nonProd.length} subdomain${isPlural ? 's' : ''} look like non-production systems${namedStr}`,
        why: "Staging and admin hosts are often less protected than the main site.",
        nextStep: "Confirm each is meant to be public, and retire or restrict the rest."
      });
    }
  }

  // Rule 5: Subdomain count (total >= 8 -> For awareness)
  if (subdomains && (subStatus === 'ok' || subdomains.count !== undefined || subdomains.subdomains)) {
    const total = subdomains.count || subdomains.total || (subdomains.subdomains && subdomains.subdomains.length) || 0;
    if (total >= 8) {
      findings.push({
        key: 'subdomains_high_count',
        ruleOrder: 5,
        severity: 'For awareness',
        severityRank: 3,
        title: `${total} subdomains appear in public certificate logs`,
        why: "Everything in certificate logs is visible to anyone, including attackers mapping your systems.",
        nextStep: "Review the list for forgotten hosts."
      });
    }
  }

  // Rule 6: Published emails (emails.length >= 1 -> For awareness)
  if (surface && (surfStatus === 'ok' || surface.emails)) {
    const emails = Array.isArray(surface.emails) ? surface.emails : [];
    if (emails.length >= 1) {
      const isPlural = emails.length !== 1;
      findings.push({
        key: 'emails_published',
        ruleOrder: 6,
        severity: 'For awareness',
        severityRank: 3,
        title: `${emails.length} email address${isPlural ? 'es' : ''} ${isPlural ? 'are' : 'is'} published on your site`,
        why: "Published addresses are the easiest targets for spear-phishing.",
        nextStep: "Consider role aliases and stricter filtering for these inboxes."
      });
    }
  }

  // Rule 7: Anything unavailable (one combined row -> For awareness)
  const unavailableList = [];
  if (rdapStatus === 'unavailable' || rdapStatus === 'error') unavailableList.push('Domain registration');
  if (sslStatus === 'unavailable' || sslStatus === 'error') unavailableList.push('TLS certificate');
  if (emailStatus === 'unavailable' || emailStatus === 'error') unavailableList.push('Email authentication');
  if (lookStatus === 'unavailable' || lookStatus === 'error') unavailableList.push('Look-alike domains');
  if (subStatus === 'unavailable' || subStatus === 'error') unavailableList.push('Certificate logs');
  if (surfStatus === 'unavailable' || surfStatus === 'error') unavailableList.push('Public website surface');

  if (state.summary && Array.isArray(state.summary.incomplete)) {
    const mapping = {
      domain_ssl: 'Domain registration',
      email_auth: 'Email authentication',
      lookalikes: 'Look-alike domains',
      subdomains: 'Certificate logs',
      exposed_surface: 'Public website surface',
      surface: 'Public website surface',
      tls: 'TLS certificate',
      rdap: 'Domain registration'
    };
    state.summary.incomplete.forEach(k => {
      const name = mapping[k] || k;
      if (!unavailableList.includes(name)) unavailableList.push(name);
    });
  }

  if (unavailableList.length >= 1) {
    const namesStr = unavailableList.length === 1 
      ? unavailableList[0] 
      : unavailableList.slice(0, -1).join(', ') + ' and ' + unavailableList[unavailableList.length - 1];

    findings.push({
      key: 'checks_unavailable',
      ruleOrder: 7,
      severity: 'For awareness',
      severityRank: 3,
      title: `${namesStr} couldn't be checked`,
      why: "A service didn't answer in time. That's not a finding, just a gap.",
      nextStep: "Run the audit again in a minute.",
      hasRetryBtn: true
    });
  }

  findings.sort((a, b) => {
    if (a.severityRank !== b.severityRank) return a.severityRank - b.severityRank;
    return a.ruleOrder - b.ruleOrder;
  });

  return findings;
}

function appendFormattedFindingTitle(containerEl, rawTitle) {
  containerEl.replaceChildren();
  if (!rawTitle) return;
  
  // Safe DOM parsing: parse text and (parentheses) with textNode
  const regex = /\(([^)]+)\)/g;
  let lastIndex = 0;
  let match;
  
  while ((match = regex.exec(rawTitle)) !== null) {
    if (match.index > lastIndex) {
      containerEl.appendChild(document.createTextNode(rawTitle.substring(lastIndex, match.index)));
    }
    containerEl.appendChild(document.createTextNode('('));
    const items = match[1].split(',');
    items.forEach((item, idx) => {
      const code = document.createElement('code');
      code.className = 'pr-mono';
      code.textContent = item.trim();
      containerEl.appendChild(code);
      if (idx < items.length - 1) {
        containerEl.appendChild(document.createTextNode(', '));
      }
    });
    containerEl.appendChild(document.createTextNode(')'));
    lastIndex = regex.lastIndex;
  }
  
  if (lastIndex < rawTitle.length) {
    containerEl.appendChild(document.createTextNode(rawTitle.substring(lastIndex)));
  }
}

function createFindingRowElement(f, existingKeys) {
  const row = document.createElement('div');
  row.className = 'pr-finding-row';
  row.setAttribute('data-finding-key', f.key);
  if (!existingKeys.has(f.key)) {
    row.classList.add('is-entering');
  }

  // 1. Marker
  const marker = document.createElement('div');
  marker.className = 'pr-finding-marker';
  marker.appendChild(createSeverityMarkerSvg(f.severity));
  row.appendChild(marker);

  // 2. Content
  const content = document.createElement('div');
  content.className = 'pr-finding-content';

  const titleRow = document.createElement('div');
  titleRow.className = 'pr-finding-title-row';

  const title = document.createElement('span');
  title.className = 'pr-finding-title';
  appendFormattedFindingTitle(title, f.title);
  titleRow.appendChild(title);

  const chip = document.createElement('span');
  chip.className = 'pr-finding-chip';
  if (f.severity === 'Fix now') chip.classList.add('pr-chip-crit');
  else if (f.severity === 'Worth a look') chip.classList.add('pr-chip-mod');
  else chip.classList.add('pr-chip-awareness');
  chip.textContent = f.severity;
  titleRow.appendChild(chip);

  content.appendChild(titleRow);

  const why = document.createElement('div');
  why.className = 'pr-finding-why';
  why.textContent = f.why;
  content.appendChild(why);

  const next = document.createElement('div');
  next.className = 'pr-finding-next';
  
  const label = document.createElement('span');
  label.className = 'pr-finding-next-label';
  label.textContent = 'Next step:';
  next.appendChild(label);

  const nextText = document.createTextNode(' ' + f.nextStep);
  next.appendChild(nextText);

  if (f.hasRetryBtn) {
    const retryBtn = document.createElement('button');
    retryBtn.type = 'button';
    retryBtn.className = 'pr-inline-retry-btn';
    retryBtn.textContent = 'Run again';
    retryBtn.onclick = handlePartialRetry;
    next.appendChild(retryBtn);
  }

  content.appendChild(next);
  row.appendChild(content);

  return row;
}

function renderStartHereSkeletons(listEl) {
  listEl.replaceChildren();
  for (let i = 0; i < 3; i++) {
    const row = document.createElement('div');
    row.className = 'pr-finding-row';
    
    const marker = document.createElement('div');
    marker.className = 'pr-finding-marker';
    const markerDot = document.createElement('div');
    markerDot.className = 'pr-skeleton-bar';
    markerDot.style.cssText = 'width: 12px; height: 12px; border-radius: 50%;';
    marker.appendChild(markerDot);
    row.appendChild(marker);

    const content = document.createElement('div');
    content.className = 'pr-finding-content';
    
    const titleBar = document.createElement('div');
    titleBar.className = 'pr-skeleton-bar';
    titleBar.style.cssText = `width: ${i === 0 ? '55%' : (i === 1 ? '68%' : '48%')}; height: 15px; margin-bottom: 8px;`;
    content.appendChild(titleBar);

    const whyBar = document.createElement('div');
    whyBar.className = 'pr-skeleton-bar';
    whyBar.style.cssText = 'width: 82%; height: 13px; margin-bottom: 6px;';
    content.appendChild(whyBar);

    const nextBar = document.createElement('div');
    nextBar.className = 'pr-skeleton-bar';
    nextBar.style.cssText = 'width: 70%; height: 13px;';
    content.appendChild(nextBar);

    row.appendChild(content);
    listEl.appendChild(row);
  }
}

function renderStartHere(state) {
  const listEl = document.getElementById('pr-findings-list');
  const extraEl = document.getElementById('pr-findings-extra');
  const wrapperEl = document.getElementById('pr-findings-extra-wrapper');
  const toggleBtn = document.getElementById('pr-findings-toggle-btn');
  if (!listEl || !extraEl) return;

  const isRunning = state.phase === 'running';
  const hasSummary = Boolean(state.summary);
  const findings = generateFindings(state);

  // If running and 0 findings generated so far -> render 3 skeleton rows
  if (isRunning && findings.length === 0 && !hasSummary) {
    if (toggleBtn) toggleBtn.style.display = 'none';
    if (wrapperEl) wrapperEl.classList.remove('is-expanded');
    isFindingsExpanded = false;
    renderStartHereSkeletons(listEl);
    extraEl.replaceChildren();
    return;
  }

  // If completed/idle and 0 findings -> Single calm row "Nothing urgent"
  if (findings.length === 0 && (hasSummary || state.phase === 'complete' || state.phase === 'idle' || state.mode === 'sample')) {
    if (toggleBtn) toggleBtn.style.display = 'none';
    if (wrapperEl) wrapperEl.classList.remove('is-expanded');
    isFindingsExpanded = false;
    extraEl.replaceChildren();
    listEl.replaceChildren();

    const calmRow = document.createElement('div');
    calmRow.className = 'pr-finding-row pr-finding-calm';

    const marker = document.createElement('div');
    marker.className = 'pr-finding-marker';
    marker.appendChild(createCalmCheckSvg());
    calmRow.appendChild(marker);

    const content = document.createElement('div');
    content.className = 'pr-finding-content';

    const titleRow = document.createElement('div');
    titleRow.className = 'pr-finding-title-row';
    const title = document.createElement('span');
    title.className = 'pr-finding-title';
    title.textContent = 'Nothing urgent';
    titleRow.appendChild(title);
    content.appendChild(titleRow);

    const facts = [];
    const rdap = state.checks?.domain?.data || state.rdap;
    const rdapStatus = state.checks?.domain?.status || state.rdap?.status;
    const ssl = state.checks?.tls?.data || state.ssl;
    const sslStatus = state.checks?.tls?.status || state.ssl?.status;
    const lookalikes = state.checks?.lookalikes?.data || state.lookalikes;
    const lookStatus = state.checks?.lookalikes?.status || state.lookalikes?.status;

    if (ssl && (sslStatus === 'ok' || ssl.valid !== undefined) && ssl.valid) {
      const proto = ssl.protocol ? ssl.protocol.replace('TLSv', 'TLS ') : 'TLS 1.3';
      const issuer = ssl.issuer || 'Example Trust CA R3';
      facts.push(`Valid ${proto} certificate from ${issuer}`);
    }
    if (rdap && (rdapStatus === 'ok' || rdap.domain_age_days !== undefined)) {
      const age = rdap.domain_age_label || (rdap.domain_age_days ? `${Math.round(rdap.domain_age_days / 365 * 10) / 10} years` : null);
      if (age) facts.push(`registered ${age} ago`);
    }
    if (lookalikes && (lookStatus === 'ok' || lookalikes.details || lookalikes.live_count !== undefined)) {
      const details = Array.isArray(lookalikes.details) ? lookalikes.details : [];
      const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length || lookalikes.live_count || 0;
      if (resolving === 0) facts.push('no look-alikes resolving');
    }
    const emailAuthFact = state.checks?.email_auth?.data || state.email_auth;
    const emailAuthStatus = state.checks?.email_auth?.status || state.email_auth?.status;
    if (emailAuthFact && (emailAuthStatus === 'ok' || emailAuthFact.dmarc)) {
      if (emailAuthFact.dmarc?.enforced && (emailAuthFact.spf?.status === 'strict' || emailAuthFact.spf?.status === 'softfail')) {
        facts.push('email authentication fully enforced (DMARC & SPF)');
      }
    }

    const why = document.createElement('div');
    why.className = 'pr-finding-why';
    const factsText = facts.length > 0 ? facts.join(', ') + '.' : '';
    why.textContent = `Every check we could run came back clean.${factsText ? ' ' + factsText : ''}`;
    content.appendChild(why);

    calmRow.appendChild(content);
    listEl.appendChild(calmRow);
    return;
  }

  // Otherwise render findings
  listEl.replaceChildren();
  extraEl.replaceChildren();

  const mainFindings = findings.slice(0, 3);
  const extraFindings = findings.slice(3);

  mainFindings.forEach((f) => {
    listEl.appendChild(createFindingRowElement(f, renderedFindingKeys));
  });

  extraFindings.forEach((f) => {
    extraEl.appendChild(createFindingRowElement(f, renderedFindingKeys));
  });

  findings.forEach(f => renderedFindingKeys.add(f.key));

  if (toggleBtn) {
    if (findings.length > 3) {
      toggleBtn.style.display = 'inline-block';
      toggleBtn.setAttribute('data-total', String(findings.length));
      toggleBtn.textContent = isFindingsExpanded ? 'Show fewer' : `Show all ${findings.length}`;
      if (wrapperEl) {
        if (isFindingsExpanded) wrapperEl.classList.add('is-expanded');
        else wrapperEl.classList.remove('is-expanded');
      }
    } else {
      toggleBtn.style.display = 'none';
      if (wrapperEl) wrapperEl.classList.remove('is-expanded');
      isFindingsExpanded = false;
    }
  }
}

function toggleFindingsExpand() {
  isFindingsExpanded = !isFindingsExpanded;
  const wrapper = document.getElementById('pr-findings-extra-wrapper');
  const btn = document.getElementById('pr-findings-toggle-btn');
  if (wrapper) {
    if (isFindingsExpanded) wrapper.classList.add('is-expanded');
    else wrapper.classList.remove('is-expanded');
  }
  if (btn) {
    const total = btn.getAttribute('data-total') || 'all';
    btn.textContent = isFindingsExpanded ? 'Show fewer' : `Show all ${total}`;
  }
}

// ── Checks Ledger Engine ───────────────────────────────────────

function computeDomainPoints(rdap) {
  if (!rdap || rdap.status !== 'ok') return 0;
  const days = rdap.domain_age_days ?? rdap.days ?? 1000;
  if (days < 30) return EXPOSURE_WEIGHTS.domain_age;
  if (days < 180) return 10;
  if (days < 365) return 6;
  if (days < 1095) return 3;
  return 0;
}

function computeSslPoints(ssl) {
  if (!ssl || ssl.status !== 'ok') return 0;
  if (ssl.valid === false) return EXPOSURE_WEIGHTS.ssl;
  const proto = (ssl.protocol || '').toUpperCase();
  if (['TLSV1', 'TLSV1.0', 'TLSV1.1', 'SSLV3', 'SSLV2'].includes(proto)) return 10;
  return 0;
}

function computeEmailAuthPoints(emailAuth) {
  if (!emailAuth || emailAuth.status !== 'ok') return 0;
  if (typeof emailAuth.points === 'number') return Math.min(emailAuth.points, EXPOSURE_WEIGHTS.email_auth);
  if (!emailAuth.has_mx) {
    if (emailAuth.spf?.status === 'strict' && emailAuth.dmarc?.status === 'reject') return 0;
    if (emailAuth.dmarc?.status === 'missing' || emailAuth.dmarc?.status === 'none') return 25;
    if (emailAuth.spf?.status === 'missing' || emailAuth.spf?.status === 'open') return 20;
    return 5;
  }
  if (emailAuth.dmarc?.status === 'missing' || emailAuth.spf?.status === 'missing' || emailAuth.spf?.status === 'open') return 25;
  if (emailAuth.dmarc?.status === 'none') return 18;
  if (emailAuth.spf?.status === 'lookup_limit_exceeded' || emailAuth.spf?.status === 'invalid') {
    return (emailAuth.dmarc?.status === 'reject' || emailAuth.dmarc?.status === 'quarantine') ? 12 : 25;
  }
  if (emailAuth.dmarc?.status === 'quarantine') {
    return emailAuth.spf?.status === 'softfail' ? 5 : 4;
  }
  if (emailAuth.dmarc?.status === 'reject') {
    return emailAuth.spf?.status === 'softfail' ? 2 : 0;
  }
  return 0;
}

function computeLookalikePoints(lookalikes) {
  if (!lookalikes || lookalikes.status !== 'ok') return 0;
  const resolving = (lookalikes.details || []).filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length;
  const liveCount = Math.max(resolving, lookalikes.live_count || 0);
  return Math.min(liveCount * 8, EXPOSURE_WEIGHTS.lookalikes);
}

function computeSubdomainPoints(subdomains) {
  if (!subdomains || subdomains.status !== 'ok') return 0;
  const count = subdomains.count || (subdomains.subdomains ? subdomains.subdomains.length : 0);
  if (count >= 20) return EXPOSURE_WEIGHTS.subdomains;
  if (count >= 10) return 6;
  if (count >= 5) return 3;
  return 0;
}

function computeSurfacePoints(surface) {
  if (!surface || surface.status !== 'ok') return 0;
  const emails = Array.isArray(surface.emails) ? surface.emails.length : 0;
  const socials = surface.socials ? Object.keys(surface.socials).length : 0;
  return Math.min(EXPOSURE_WEIGHTS.surface, Math.min(emails, 4) * 2 + Math.min(socials, 2));
}

function getGradeAndRamp(points, maxPoints, isUnavailableOrPending) {
  if (isUnavailableOrPending) {
    return { grade: '—', ramp: 'unavailable', pct: 0 };
  }
  const pct = Math.max(0, Math.min(100, Math.round((points / maxPoints) * 100)));
  let grade = 'A';
  let ramp = 'low';

  if (pct === 0) {
    grade = 'A';
    ramp = 'low';
  } else if (pct <= 20) {
    grade = 'B';
    ramp = 'low';
  } else if (pct <= 45) {
    grade = 'C';
    ramp = 'mod';
  } else if (pct <= 70) {
    grade = 'D';
    ramp = 'high';
  } else {
    grade = 'F';
    ramp = 'crit';
  }

  return { grade, ramp, pct };
}

function renderChecksLedger(state) {
  const container = document.getElementById('pr-checks-list');
  if (!container) return;

  const rdap = state.checks?.domain?.data || state.rdap;
  const rdapStatus = state.checks?.domain?.status || state.rdap?.status;

  const ssl = state.checks?.tls?.data || state.ssl;
  const sslStatus = state.checks?.tls?.status || state.ssl?.status;

  const emailAuth = state.checks?.email_auth?.data || state.email_auth;
  const emailStatus = state.checks?.email_auth?.status || state.email_auth?.status;

  const lookalikes = state.checks?.lookalikes?.data || state.lookalikes;
  const lookStatus = state.checks?.lookalikes?.status || state.lookalikes?.status;

  const subdomains = state.checks?.subdomains?.data || state.subdomains;
  const subStatus = state.checks?.subdomains?.status || state.subdomains?.status;

  const surface = state.checks?.surface?.data || state.surface;
  const surfStatus = state.checks?.surface?.status || state.surface?.status;

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isDomainIncomplete = incomplete.some(s => s.includes('domain') || s.includes('rdap'));
  const isTlsIncomplete = incomplete.some(s => s.includes('tls') || s.includes('ssl') || s.includes('certificate'));
  const isEmailIncomplete = incomplete.some(s => s.includes('email') || s.includes('auth') || s.includes('dmarc') || s.includes('spf'));
  const isLookIncomplete = incomplete.some(s => s.includes('look'));
  const isSubIncomplete = incomplete.some(s => s.includes('subdomain'));
  const isSurfIncomplete = incomplete.some(s => s.includes('surface') || s.includes('public'));

  const checks = [
    {
      id: 'domain',
      name: 'Domain age and registration',
      maxPoints: EXPOSURE_WEIGHTS.domain_age,
      getPoints: (s) => {
        if (isDomainIncomplete || rdapStatus === 'unavailable' || rdapStatus === 'error') return 0;
        return s.scoring?.domain_points ?? (s.summary?.score_breakdown?.domain_age_points ?? computeDomainPoints(rdap));
      },
      getStatus: (s) => {
        if (isDomainIncomplete) return 'unavailable';
        if (rdapStatus === 'unavailable' || rdapStatus === 'error') return 'unavailable';
        if (rdap && (rdapStatus === 'ok' || rdap.domain_age_days !== undefined)) return 'ok';
        if (s.phase === 'running' && (s.stage === 'domain_ssl' || s.stage === 'init')) return 'running';
        if (s.phase === 'complete' || s.summary) return (rdap ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isDomainIncomplete || rdapStatus === 'unavailable' || rdapStatus === 'error') ? 'unavailable' :
                   (rdap && (rdapStatus === 'ok' || rdap.domain_age_days !== undefined)) ? 'ok' :
                   (s.phase === 'running' && (s.stage === 'domain_ssl' || s.stage === 'init')) ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Registration data couldn't be retrieved · Not a finding";
        const age = rdap?.domain_age_label || (rdap?.domain_age_days ? `${Math.round(rdap.domain_age_days / 365 * 10) / 10} years` : 'recent');
        const reg = rdap?.registrar || 'Example Registrar, Inc.';
        return `Registered ${age} ago with ${reg}`;
      }
    },
    {
      id: 'tls',
      name: 'TLS certificate',
      maxPoints: EXPOSURE_WEIGHTS.ssl,
      getPoints: (s) => {
        if (isTlsIncomplete || sslStatus === 'unavailable' || sslStatus === 'error') return 0;
        return s.scoring?.ssl_points ?? (s.summary?.score_breakdown?.ssl_points ?? computeSslPoints(ssl));
      },
      getStatus: (s) => {
        if (isTlsIncomplete) return 'unavailable';
        if (sslStatus === 'unavailable' || sslStatus === 'error') return 'unavailable';
        if (ssl && (sslStatus === 'ok' || ssl.valid !== undefined)) return 'ok';
        if (s.phase === 'running' && (s.stage === 'domain_ssl' || s.stage === 'init')) return 'running';
        if (s.phase === 'complete' || s.summary) return (ssl ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isTlsIncomplete || sslStatus === 'unavailable' || sslStatus === 'error') ? 'unavailable' :
                   (ssl && (sslStatus === 'ok' || ssl.valid !== undefined)) ? 'ok' :
                   (s.phase === 'running' && (s.stage === 'domain_ssl' || s.stage === 'init')) ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Certificate couldn't be tested · Not a finding";
        if (ssl?.valid) {
          const proto = ssl.protocol ? ssl.protocol.replace('TLSv', 'TLS ') : 'TLS 1.3';
          const issuer = ssl.issuer || 'Example Trust CA R3';
          return `${proto} certificate from ${issuer}`;
        }
        if (ssl?.error && ssl.error.includes('expired')) return "No valid certificate (expired)";
        if (ssl?.error && ssl.error.includes('self-signed')) return "No valid certificate (self-signed)";
        return "No valid certificate";
      }
    },
    {
      id: 'email_auth',
      name: 'Email authentication',
      maxPoints: EXPOSURE_WEIGHTS.email_auth,
      getPoints: (s) => {
        if (isEmailIncomplete || emailStatus === 'unavailable' || emailStatus === 'error') return 0;
        return s.scoring?.email_auth_points ?? (s.summary?.score_breakdown?.email_auth_points ?? computeEmailAuthPoints(emailAuth));
      },
      getStatus: (s) => {
        if (isEmailIncomplete) return 'unavailable';
        if (emailStatus === 'unavailable' || emailStatus === 'error') return 'unavailable';
        if (emailAuth && (emailStatus === 'ok' || emailAuth.dmarc || emailAuth.spf)) return 'ok';
        if (s.phase === 'running' && s.stage === 'email_auth') return 'running';
        if (s.phase === 'complete' || s.summary) return (emailAuth ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isEmailIncomplete || emailStatus === 'unavailable' || emailStatus === 'error') ? 'unavailable' :
                   (emailAuth && (emailStatus === 'ok' || emailAuth.dmarc || emailAuth.spf)) ? 'ok' :
                   (s.phase === 'running' && s.stage === 'email_auth') ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Couldn't be verified · Not a finding";
        if (emailAuth && !emailAuth.has_mx) {
          if (emailAuth.dmarc?.enforced && emailAuth.spf?.status === 'strict') {
            return "No mail received · Protected with SPF -all & DMARC reject";
          }
          return "No mail received · Incomplete protection";
        }
        const dmarcGrade = emailAuth?.dmarc?.grade || (emailAuth?.dmarc?.status === 'missing' ? 'DMARC missing' : 'DMARC active');
        const spfGrade = emailAuth?.spf?.grade || (emailAuth?.spf?.status === 'missing' ? 'SPF missing' : 'SPF active');
        return `${dmarcGrade} · ${spfGrade}`;
      }
    },
    {
      id: 'lookalikes',
      name: 'Look-alike domains',
      maxPoints: EXPOSURE_WEIGHTS.lookalikes,
      getPoints: (s) => {
        if (isLookIncomplete || lookStatus === 'unavailable' || lookStatus === 'error') return 0;
        return s.scoring?.lookalikes_points ?? (s.summary?.score_breakdown?.lookalikes_points ?? computeLookalikePoints(lookalikes));
      },
      getStatus: (s) => {
        if (isLookIncomplete) return 'unavailable';
        if (lookStatus === 'unavailable' || lookStatus === 'error') return 'unavailable';
        if (lookalikes && (lookStatus === 'ok' || lookalikes.details || lookalikes.live_count !== undefined)) return 'ok';
        if (s.phase === 'running' && s.stage === 'lookalikes') return 'running';
        if (s.phase === 'complete' || s.summary) return (lookalikes ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isLookIncomplete || lookStatus === 'unavailable' || lookStatus === 'error') ? 'unavailable' :
                   (lookalikes && (lookStatus === 'ok' || lookalikes.details || lookalikes.live_count !== undefined)) ? 'ok' :
                   (s.phase === 'running' && s.stage === 'lookalikes') ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Couldn't be checked · Not a finding";
        const details = Array.isArray(lookalikes?.details) ? lookalikes.details : [];
        const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length || lookalikes?.resolving_count || lookalikes?.live_count || 0;
        const total = lookalikes?.candidates_count || details.length || 6;
        const untested = details.filter(d => d.status === 'unknown' || d.resolves === null).length || lookalikes?.unknown_count || 0;
        if (resolving > 0) {
          const untestedStr = untested > 0 ? `, ${untested} more couldn't be tested` : '';
          return `${resolving} of ${total} variants resolve${untestedStr}`;
        }
        return `None of ${total} variants resolve`;
      }
    },
    {
      id: 'subdomains',
      name: 'Subdomains in certificate logs',
      maxPoints: EXPOSURE_WEIGHTS.subdomains,
      getPoints: (s) => {
        if (isSubIncomplete || subStatus === 'unavailable' || subStatus === 'error') return 0;
        return s.scoring?.subdomains_points ?? (s.summary?.score_breakdown?.subdomains_points ?? computeSubdomainPoints(subdomains));
      },
      getStatus: (s) => {
        if (isSubIncomplete) return 'unavailable';
        if (subStatus === 'unavailable' || subStatus === 'error') return 'unavailable';
        if (subdomains && (subStatus === 'ok' || subdomains.subdomains)) return 'ok';
        if (s.phase === 'running' && s.stage === 'subdomains') return 'running';
        if (s.phase === 'complete' || s.summary) return (subdomains ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isSubIncomplete || subStatus === 'unavailable' || subStatus === 'error') ? 'unavailable' :
                   (subdomains && (subStatus === 'ok' || subdomains.subdomains)) ? 'ok' :
                   (s.phase === 'running' && s.stage === 'subdomains') ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Couldn't be checked · Not a finding";
        const count = subdomains?.count ?? (subdomains?.subdomains ? subdomains.subdomains.length : 0);
        const shown = subdomains?.subdomains ? subdomains.subdomains.length : count;
        if (count === 0) return "None found in certificate logs";
        return `${count} found, showing ${Math.min(count, shown)}`;
      }
    },
    {
      id: 'surface',
      name: 'Public website surface',
      maxPoints: EXPOSURE_WEIGHTS.surface,
      getPoints: (s) => {
        if (isSurfIncomplete || surfStatus === 'unavailable' || surfStatus === 'error') return 0;
        return s.scoring?.surface_points ?? (s.summary?.score_breakdown?.surface_points ?? computeSurfacePoints(surface));
      },
      getStatus: (s) => {
        if (isSurfIncomplete) return 'unavailable';
        if (surfStatus === 'unavailable' || surfStatus === 'error') return 'unavailable';
        if (surface && (surfStatus === 'ok' || surface.emails || surface.blocked !== undefined)) return 'ok';
        if (s.phase === 'running' && s.stage === 'exposed_surface') return 'running';
        if (s.phase === 'complete' || s.summary) return (surface ? 'ok' : 'unavailable');
        return 'pending';
      },
      getResultText: (s) => {
        const st = (isSurfIncomplete || surfStatus === 'unavailable' || surfStatus === 'error') ? 'unavailable' :
                   (surface && (surfStatus === 'ok' || surface.emails || surface.blocked !== undefined)) ? 'ok' :
                   (s.phase === 'running' && s.stage === 'exposed_surface') ? 'running' : 'pending';
        if (st === 'pending') return '';
        if (st === 'running') return 'Checking';
        if (st === 'unavailable') return "Couldn't be retrieved · Not a finding";
        if (surface?.blocked) return "The site blocked automated retrieval · Not a finding";
        const emails = (surface?.emails || []).length;
        const socials = surface?.socials ? Object.keys(surface.socials).length : (surface?.socials_count || 0);
        if (emails > 0 || socials > 0) {
          const emailPart = `${emails} email${emails === 1 ? '' : 's'}`;
          const socialPart = `${socials} profile${socials === 1 ? '' : 's'}`;
          return `${emailPart} and ${socialPart} published`;
        }
        return "No public emails or social profiles detected";
      }
    }
  ];

  container.replaceChildren();

  checks.forEach((chk) => {
    const status = chk.getStatus(state);
    const resultText = chk.getResultText(state);
    const points = chk.getPoints(state);
    const maxPoints = chk.maxPoints;
    const isUnavailable = status === 'unavailable';
    const isPending = status === 'pending';
    const isRunning = status === 'running';

    const { grade, ramp, pct } = getGradeAndRamp(points, maxPoints, isUnavailable || isPending || isRunning);

    const row = document.createElement('div');
    row.className = 'pr-check-row';
    row.setAttribute('role', 'listitem');
    row.setAttribute('tabindex', '0');
    row.setAttribute('data-check-id', chk.id);
    row.onclick = () => handleCheckRowClick(chk.id);
    row.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleCheckRowClick(chk.id);
      }
    };

    // Column 1: Info (Name + Result line)
    const infoCol = document.createElement('div');
    infoCol.className = 'pr-check-info';

    const name = document.createElement('span');
    name.className = 'pr-check-name';
    name.textContent = chk.name;
    infoCol.appendChild(name);

    if (isPending) {
      const skel = document.createElement('div');
      skel.className = 'pr-skeleton-bar';
      skel.style.cssText = 'width: 140px; height: 12px; margin-top: 3px;';
      infoCol.appendChild(skel);
    } else {
      const res = document.createElement('span');
      res.className = 'pr-check-result';
      if (isRunning) res.classList.add('is-running');
      res.textContent = resultText;
      infoCol.appendChild(res);
    }
    row.appendChild(infoCol);

    // Column 2: Meter Track
    const meterCol = document.createElement('div');
    meterCol.className = 'pr-check-meter-col';
    const track = document.createElement('div');
    track.className = 'pr-check-track';
    if (isUnavailable) {
      track.classList.add('is-unavailable');
    } else {
      const fill = document.createElement('div');
      fill.className = 'pr-check-fill';
      fill.setAttribute('data-ramp', ramp);
      if (!isPending && !isRunning) {
        fill.style.width = `${pct}%`;
      }
      track.appendChild(fill);
    }
    meterCol.appendChild(track);
    row.appendChild(meterCol);

    // Column 3: Points Text
    const pointsCol = document.createElement('div');
    pointsCol.className = 'pr-check-points';
    if (isUnavailable) {
      pointsCol.classList.add('is-unavailable');
      pointsCol.textContent = 'Not assessed';
    } else if (isPending || isRunning) {
      pointsCol.textContent = '—';
    } else {
      pointsCol.textContent = `${points} of ${maxPoints}`;
    }
    row.appendChild(pointsCol);

    // Column 4: Grade Badge
    const gradeCol = document.createElement('div');
    gradeCol.className = 'pr-check-grade-col';
    const badge = document.createElement('div');
    badge.className = 'pr-check-grade';

    if (isUnavailable || isPending || isRunning) {
      badge.classList.add('pr-grade-dash');
      badge.textContent = '—';
    } else {
      badge.classList.add(`pr-grade-${grade.toLowerCase()}`);
      badge.textContent = grade;
    }
    gradeCol.appendChild(badge);
    row.appendChild(gradeCol);

    container.appendChild(row);
  });
}

// ════════════════════════════════════════════════════════════════
// PART 7: EVIDENCE ACCORDIONS & ANALYST NOTE ENGINE
// ════════════════════════════════════════════════════════════════

const autoOpenedAccordions = new Set();
const userManuallyToggledAccordions = new Set();

function formatExpiryDate(raw) {
  if (!raw) return "Couldn't be checked";
  try {
    const d = new Date(raw);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }
  } catch (e) {}
  return String(raw).trim();
}

function isExpiringSoon(raw) {
  if (!raw) return false;
  try {
    const d = new Date(raw);
    if (!isNaN(d.getTime())) {
      const diffMs = d.getTime() - Date.now();
      const diffDays = diffMs / (1000 * 60 * 60 * 24);
      return diffDays >= 0 && diffDays <= 30;
    }
  } catch (e) {}
  return false;
}

function sanitizeExternalUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') return null;
  const trimmed = rawUrl.trim();
  try {
    const parsed = new URL(trimmed.startsWith('http://') || trimmed.startsWith('https://') ? trimmed : `https://${trimmed}`);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      return parsed.href;
    }
  } catch (e) {}
  return null;
}

function copyTextToClipboard(text, btnElement) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (btnElement) {
      const originalText = btnElement.textContent;
      btnElement.textContent = 'Copied!';
      setTimeout(() => {
        btnElement.textContent = originalText;
      }, 1500);
    }
  }).catch(() => {});
}

function copyAllSubdomains(btnElement) {
  const pills = document.querySelectorAll('#pr-subdomains-pills .pr-pill-text');
  const hosts = Array.from(pills).map(p => p.textContent.trim()).filter(Boolean);
  if (hosts.length > 0) {
    copyTextToClipboard(hosts.join('\n'), btnElement);
  }
}

function initAccordionListeners() {
  document.querySelectorAll('.pr-accordion').forEach(det => {
    det.addEventListener('toggle', () => {
      const section = det.getAttribute('data-check-section') || det.id;
      if (section) userManuallyToggledAccordions.add(section);
    });
  });
}

function renderEvidenceDomainCert(state) {
  const metaEl = document.getElementById('pr-meta-domain-cert');
  const listEl = document.getElementById('pr-domain-cert-list');
  if (!listEl) return;

  const rdap = state.checks?.domain?.data || state.rdap;
  const rdapStatus = state.checks?.domain?.status || state.rdap?.status;
  const ssl = state.checks?.tls?.data || state.ssl;
  const sslStatus = state.checks?.tls?.status || state.ssl?.status;

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isRdapUnavail = rdapStatus === 'unavailable' || rdapStatus === 'error' || incomplete.some(s => s.includes('domain') || s.includes('rdap'));
  const isSslUnavail = sslStatus === 'unavailable' || sslStatus === 'error' || incomplete.some(s => s.includes('tls') || s.includes('ssl') || s.includes('certificate'));

  // Summary meta text
  if (metaEl) {
    if (rdap && !isRdapUnavail) {
      const age = rdap.domain_age_label || (rdap.domain_age_days ? `${Math.round(rdap.domain_age_days / 365 * 10) / 10}y` : '');
      const tlsPart = ssl && ssl.valid ? 'TLS valid' : (ssl && ssl.valid === false ? 'TLS invalid' : (isSslUnavail ? 'TLS gap' : ''));
      metaEl.textContent = [age ? `Registered ${age} ago` : '', tlsPart].filter(Boolean).join(' · ');
    } else if (isRdapUnavail && isSslUnavail) {
      metaEl.textContent = "Couldn't be checked";
    } else {
      metaEl.textContent = '';
    }
  }

  listEl.replaceChildren();

  function createDefItem(term, valText, isUnavail, chipText, chipType) {
    const item = document.createElement('div');
    item.className = 'pr-def-item';

    const dt = document.createElement('dt');
    dt.className = 'pr-def-term';
    dt.textContent = term;
    item.appendChild(dt);

    const dd = document.createElement('dd');
    dd.className = 'pr-def-val';

    if (isUnavail) {
      const unavailSpan = document.createElement('span');
      unavailSpan.className = 'pr-unavail-val';
      {
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 16 16'); svg.setAttribute('width', '13'); svg.setAttribute('height', '13');
      svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('stroke-width', '1.5');
      svg.setAttribute('aria-hidden', 'true');
      const c = document.createElementNS(SVG_NS, 'circle'); c.setAttribute('cx', '8'); c.setAttribute('cy', '8'); c.setAttribute('r', '6'); svg.appendChild(c);
      const l = document.createElementNS(SVG_NS, 'line'); l.setAttribute('x1', '8'); l.setAttribute('y1', '7'); l.setAttribute('x2', '8'); l.setAttribute('y2', '11'); svg.appendChild(l);
      const d = document.createElementNS(SVG_NS, 'circle'); d.setAttribute('cx', '8'); d.setAttribute('cy', '5'); d.setAttribute('r', '0.75'); d.setAttribute('fill', 'currentColor'); svg.appendChild(d);
      unavailSpan.appendChild(svg);
    }
      const txt = document.createTextNode(" Couldn't be checked");
      unavailSpan.appendChild(txt);
      dd.appendChild(unavailSpan);
    } else {
      const txt = document.createTextNode(valText || 'Unknown');
      dd.appendChild(txt);

      if (chipText) {
        const chip = document.createElement('span');
        chip.className = `pr-chip ${chipType === 'mod' ? 'pr-chip-mod' : 'pr-chip-crit'}`;
        chip.textContent = chipText;
        dd.appendChild(chip);
      }
    }

    item.appendChild(dd);
    return item;
  }

  // 1. Registered
  const regDate = rdap?.created_date || rdap?.registered_date || (!isRdapUnavail && rdap ? 'Unknown' : null);
  listEl.appendChild(createDefItem('Registered', regDate, isRdapUnavail || (!regDate && rdapStatus !== 'ok')));

  // 2. Expires
  const expDate = rdap?.expiration_date || (!isRdapUnavail && rdap ? 'Unknown' : null);
  listEl.appendChild(createDefItem('Expires', expDate, isRdapUnavail || (!expDate && rdapStatus !== 'ok')));

  // 3. Age
  const ageLabel = rdap?.domain_age_label || (rdap?.domain_age_days ? `${Math.round(rdap.domain_age_days / 365 * 10) / 10} years` : (!isRdapUnavail && rdap ? 'Unknown' : null));
  const isRecent = typeof rdap?.domain_age_days === 'number' && rdap.domain_age_days < 180;
  listEl.appendChild(createDefItem('Age', ageLabel, isRdapUnavail || (!ageLabel && rdapStatus !== 'ok'), isRecent ? 'Recent' : null, 'mod'));

  // 4. Registrar
  const registrar = rdap?.registrar || (!isRdapUnavail && rdap ? 'Example Registrar, Inc.' : null);
  listEl.appendChild(createDefItem('Registrar', registrar, isRdapUnavail || (!registrar && rdapStatus !== 'ok')));

  // 5. TLS protocol
  const protocol = ssl?.protocol ? ssl.protocol.replace('TLSv', 'TLS ') : (!isSslUnavail && ssl ? (ssl.valid ? 'TLS 1.3' : 'None') : null);
  listEl.appendChild(createDefItem('TLS protocol', protocol, isSslUnavail || (!protocol && sslStatus !== 'ok')));

  // 6. Certificate issuer
  const issuer = ssl?.issuer || (!isSslUnavail && ssl ? (ssl.valid ? 'Example Trust CA R3' : 'No certificate') : null);
  listEl.appendChild(createDefItem('Certificate issuer', issuer, isSslUnavail || (!issuer && sslStatus !== 'ok')));

  // 7. Certificate valid until
  const certExpiry = ssl?.expiry ? formatExpiryDate(ssl.expiry) : (!isSslUnavail && ssl ? (ssl.valid ? 'Valid' : 'No valid certificate') : null);
  const expiringSoon = ssl?.expiry && isExpiringSoon(ssl.expiry);
  listEl.appendChild(createDefItem('Certificate valid until', certExpiry, isSslUnavail || (!certExpiry && sslStatus !== 'ok'), expiringSoon ? 'Expires soon' : null, 'mod'));
}

function createEmailDefItem(term, factText, badgeEl, rawRecordText, emptyLabel) {
  const item = document.createElement('div');
  item.className = 'pr-def-item';

  const dt = document.createElement('dt');
  dt.className = 'pr-def-term';
  dt.textContent = term;
  item.appendChild(dt);

  const dd = document.createElement('dd');
  dd.className = 'pr-def-val';

  const factSpan = document.createElement('span');
  factSpan.style.marginRight = '8px';
  factSpan.textContent = factText;
  dd.appendChild(factSpan);

  if (badgeEl) {
    dd.appendChild(badgeEl);
  }

  const rawEl = document.createElement('div');
  rawEl.className = 'pr-raw-record';
  if (rawRecordText && String(rawRecordText).trim()) {
    rawEl.textContent = String(rawRecordText).trim();
  } else {
    rawEl.classList.add('pr-raw-record-empty');
    rawEl.textContent = emptyLabel || 'None published';
  }
  dd.appendChild(rawEl);

  item.appendChild(dd);
  return item;
}

function createShapeBadge(shapeClass, styleClass, text) {
  const wrap = document.createElement('span');
  wrap.className = `pr-badge-shape-wrap ${styleClass}`;
  const shape = document.createElement('span');
  shape.className = `pr-badge-shape ${shapeClass}`;
  wrap.appendChild(shape);
  const label = document.createElement('span');
  label.textContent = text;
  wrap.appendChild(label);
  return wrap;
}

function renderEvidenceEmailAuth(state) {
  const introEl = document.getElementById('pr-email-auth-intro');
  const listEl = document.getElementById('pr-email-auth-list');
  if (!listEl) return;

  const emailAuth = state.checks?.email_auth?.data || state.email_auth;
  const emailStatus = state.checks?.email_auth?.status || state.email_auth?.status;

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isEmailIncomplete = emailStatus === 'unavailable' || emailStatus === 'error' || incomplete.some(s => s.includes('email') || s.includes('auth') || s.includes('dmarc') || s.includes('spf'));

  listEl.replaceChildren();

  if (isEmailIncomplete) {
    if (introEl) introEl.textContent = "Email authentication records couldn't be retrieved · Not a finding";
    const item = document.createElement('div');
    item.className = 'pr-def-item';
    const dd = document.createElement('dd');
    dd.className = 'pr-def-val';
    const unavailSpan = document.createElement('span');
    unavailSpan.className = 'pr-unavail-val';
    unavailSpan.textContent = "DNS queries for SPF, DMARC, MTA-STS and TLS-RPT timed out or could not be completed.";
    dd.appendChild(unavailSpan);
    item.appendChild(dd);
    listEl.appendChild(item);
    return;
  }

  if (!emailAuth || (!emailAuth.spf && !emailAuth.dmarc && emailStatus !== 'ok')) {
    if (introEl) introEl.textContent = state.phase === 'running' ? "Checking SPF, DMARC, MTA-STS, and DKIM..." : "Email authentication pending";
    return;
  }

  if (introEl) {
    introEl.textContent = emailAuth.overall_summary || (emailAuth.dmarc?.enforced ? "Domain has active email authentication policies." : "Email authentication policies evaluated.");
  }

  // 1. Inbound mail & MX records
  const mxRecords = (emailAuth.raw_records?.mx && Array.isArray(emailAuth.raw_records.mx)) ? emailAuth.raw_records.mx : [];
  const mxFact = emailAuth.has_mx
    ? `Domain receives mail (${mxRecords.length > 0 ? mxRecords.length + ' MX records' : 'MX configured'})`
    : (emailAuth.is_null_mx ? "RFC 7505 Null MX record published (0 .)" : "No MX records published (does not receive mail)");
  const mxBadge = emailAuth.has_mx
    ? createShapeBadge('pr-shape-circle', 'is-enforced', 'Active MX')
    : createShapeBadge('pr-shape-ring', 'is-neutral', 'No mail domain');
  const mxRaw = mxRecords.length > 0 ? mxRecords.join('\n') : (emailAuth.has_mx ? 'Active MX present' : (emailAuth.is_null_mx ? '0 .' : 'None'));
  listEl.appendChild(createEmailDefItem('Inbound mail (MX)', mxFact, mxBadge, mxRaw, 'No MX records'));

  // 2. SPF (Sender Policy Framework)
  const spfStatus = emailAuth.spf?.status;
  const spfDetail = emailAuth.spf?.detail || (spfStatus === 'missing' ? 'No SPF record published' : 'SPF evaluated');
  let spfBadge;
  if (spfStatus === 'strict') {
    spfBadge = createShapeBadge('pr-shape-circle', 'is-enforced', 'Strict (-all)');
  } else if (spfStatus === 'softfail') {
    spfBadge = createShapeBadge('pr-shape-triangle', 'is-softfail', 'Soft fail (~all)');
  } else if (spfStatus === 'lookup_limit_exceeded' || spfStatus === 'invalid') {
    spfBadge = createShapeBadge('pr-shape-square', 'is-broken', emailAuth.spf?.grade || 'Broken');
  } else if (spfStatus === 'missing' || spfStatus === 'open' || spfStatus === 'neutral') {
    spfBadge = createShapeBadge('pr-shape-diamond', 'is-exposed', emailAuth.spf?.grade || 'Exposed');
  } else {
    spfBadge = createShapeBadge('pr-shape-ring', 'is-neutral', emailAuth.spf?.grade || 'Unknown');
  }
  const spfRaw = emailAuth.spf?.raw_record || emailAuth.raw_records?.spf || 'None published';
  listEl.appendChild(createEmailDefItem('SPF (TXT)', spfDetail, spfBadge, spfRaw, 'No SPF record published'));

  // 3. DMARC
  const dmarcStatus = emailAuth.dmarc?.status;
  const dmarcDetail = emailAuth.dmarc?.detail || (dmarcStatus === 'missing' ? 'No DMARC record published' : 'DMARC evaluated');
  let dmarcBadge;
  if (dmarcStatus === 'reject') {
    dmarcBadge = createShapeBadge('pr-shape-circle', 'is-enforced', 'Enforced (p=reject)');
  } else if (dmarcStatus === 'quarantine') {
    dmarcBadge = createShapeBadge('pr-shape-circle', 'is-enforced', 'Enforced (p=quarantine)');
  } else if (dmarcStatus === 'none') {
    dmarcBadge = createShapeBadge('pr-shape-triangle', 'is-monitoring', 'Monitoring only (p=none)');
  } else if (dmarcStatus === 'missing') {
    dmarcBadge = createShapeBadge('pr-shape-diamond', 'is-missing', 'Missing (exposed)');
  } else {
    dmarcBadge = createShapeBadge('pr-shape-square', 'is-broken', emailAuth.dmarc?.grade || 'Invalid');
  }
  const dmarcRaw = emailAuth.dmarc?.raw_record || emailAuth.raw_records?.dmarc || 'None published';
  listEl.appendChild(createEmailDefItem('DMARC (TXT _dmarc)', dmarcDetail, dmarcBadge, dmarcRaw, 'No DMARC record published'));

  // 4. MTA-STS
  const hasMtaSts = Boolean(emailAuth.mta_sts?.present);
  const mtaStsFact = hasMtaSts ? 'MTA-STS policy record published' : 'No MTA-STS policy record detected';
  const mtaStsBadge = hasMtaSts
    ? createShapeBadge('pr-shape-circle', 'is-enforced', 'Published')
    : createShapeBadge('pr-shape-ring', 'is-neutral', 'Not configured');
  const mtaStsRaw = emailAuth.mta_sts?.raw_record || emailAuth.raw_records?.mta_sts || 'None published';
  listEl.appendChild(createEmailDefItem('MTA-STS (TXT _mta-sts)', mtaStsFact, mtaStsBadge, mtaStsRaw, 'No MTA-STS record published'));

  // 5. TLS-RPT
  const hasTlsRpt = Boolean(emailAuth.tls_rpt?.present);
  const tlsRptFact = hasTlsRpt ? 'SMTP TLS reporting enabled via _smtp._tls' : 'No TLS-RPT record detected';
  const tlsRptBadge = hasTlsRpt
    ? createShapeBadge('pr-shape-circle', 'is-enforced', 'Enabled')
    : createShapeBadge('pr-shape-ring', 'is-neutral', 'Not configured');
  const tlsRptRaw = emailAuth.tls_rpt?.raw_record || emailAuth.raw_records?.tls_rpt || 'None published';
  listEl.appendChild(createEmailDefItem('TLS-RPT (TXT _smtp._tls)', tlsRptFact, tlsRptBadge, tlsRptRaw, 'No TLS-RPT record published'));

  // 6. DKIM (Probed common selectors; never claims absent)
  const dkimFound = emailAuth.dkim?.status === 'found';
  const dkimDetail = emailAuth.dkim?.detail || "Not detected with common selectors (this does not mean it's absent)";
  const dkimBadge = dkimFound
    ? createShapeBadge('pr-shape-circle', 'is-enforced', `Found (selector: ${emailAuth.dkim?.selector || 'unknown'})`)
    : createShapeBadge('pr-shape-ring', 'is-neutral', 'Not detected (common selectors)');
  const dkimRaw = emailAuth.dkim?.raw_record || emailAuth.raw_records?.dkim || 'None detected across probed common selectors (default, google, selector1, selector2, k1, s1, mandrill, dkim)';
  listEl.appendChild(createEmailDefItem('DKIM (DomainKeys)', dkimDetail, dkimBadge, dkimRaw, 'None detected with common selectors'));
}

function renderEvidenceLookalikes(state) {
  const metaEl = document.getElementById('pr-meta-lookalikes');
  const introEl = document.getElementById('pr-lookalikes-intro');
  const listEl = document.getElementById('pr-lookalikes-list');
  if (!listEl) return;

  const lookalikes = state.checks?.lookalikes?.data || state.lookalikes;
  const lookStatus = state.checks?.lookalikes?.status || state.lookalikes?.status;
  const domain = state.domain || 'acme.example';

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isUnavail = lookStatus === 'unavailable' || lookStatus === 'error' || incomplete.some(s => s.includes('look'));

  const details = Array.isArray(lookalikes?.details) ? lookalikes.details : [];
  const candidatesCount = lookalikes?.candidates_count || details.length || 6;

  if (metaEl) {
    if (isUnavail) {
      metaEl.textContent = "Couldn't be checked";
    } else if (lookalikes && (lookStatus === 'ok' || details.length > 0)) {
      const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length || lookalikes.live_count || 0;
      metaEl.textContent = resolving > 0 ? `${resolving} of ${candidatesCount} resolve` : `None of ${candidatesCount} resolve`;
    } else {
      metaEl.textContent = '';
    }
  }

  if (introEl) {
    introEl.textContent = `We generated ${candidatesCount} likely misspellings and variants of ${domain} and looked each one up in DNS.`;
  }

  listEl.replaceChildren();

  if (isUnavail || details.length === 0) {
    const emptyRow = document.createElement('div');
    emptyRow.className = 'pr-evidence-note';
    emptyRow.textContent = isUnavail 
      ? "Look-alike domain checks couldn't be completed. A DNS service didn't answer in time."
      : "No look-alike domain candidates generated.";
    listEl.appendChild(emptyRow);
    return;
  }

  // Sort order:
  // 1. Live Web Server (active threat)
  // 2. Registered (DNS only / parked)
  // 3. Official Brand Redirect / Points to own servers
  // 4. Unknown
  // 5. Not found / Available
  const sorted = [...details].sort((a, b) => {
    const isLiveA = a.state === 'resolves' || a.status === 'resolves' || a.is_live || a.resolves;
    const isLiveB = b.state === 'resolves' || b.status === 'resolves' || b.is_live || b.resolves;
    const ownA = Boolean(a.same_infrastructure || a.is_brand_redirect || a.web_status === 'redirect');
    const ownB = Boolean(b.same_infrastructure || b.is_brand_redirect || b.web_status === 'redirect');
    const actA = isLiveA && a.web_status === 'active';
    const actB = isLiveB && b.web_status === 'active';
    const unkA = a.status === 'unknown' || a.resolves === null;
    const unkB = b.status === 'unknown' || b.resolves === null;

    const rankA = actA ? 1 : (isLiveA && !ownA ? 2 : (ownA ? 3 : (unkA ? 4 : 5)));
    const rankB = actB ? 1 : (isLiveB && !ownB ? 2 : (ownB ? 3 : (unkB ? 4 : 5)));

    return rankA - rankB;
  });

  sorted.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'pr-lookalike-row';
    row.setAttribute('data-evidence-item', item.domain);

    // Left: domain + IP
    const left = document.createElement('div');
    left.className = 'pr-lookalike-left';

    const domCode = document.createElement('code');
    domCode.className = 'pr-mono pr-lookalike-domain';
    domCode.textContent = item.domain;
    left.appendChild(domCode);

    if (item.ip) {
      const ipSpan = document.createElement('span');
      ipSpan.className = 'pr-lookalike-ip';
      ipSpan.textContent = item.ip;
      left.appendChild(ipSpan);
    }
    row.appendChild(left);

    // Right: status + button
    const right = document.createElement('div');
    right.className = 'pr-lookalike-right';

    const isLive = item.state === 'resolves' || item.state === 'resolves' || item.status === 'resolves' || item.is_live || item.resolves;
    const isOwn = Boolean(item.same_infrastructure || item.is_brand_redirect || item.web_status === 'redirect');
    const isUnk = item.status === 'unknown' || item.resolves === null;
    const webStatus = item.web_status || (isLive ? (isOwn ? 'redirect' : 'dns_only') : 'none');

    const statusSpan = document.createElement('span');
    statusSpan.className = 'pr-lookalike-status';

    if (isLive && isOwn) {
      statusSpan.classList.add('pr-status-low');
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 12 12'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10');
      svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'var(--pr-low)'); svg.setAttribute('stroke-width', '2');
      svg.setAttribute('aria-hidden', 'true');
      const c = document.createElementNS(SVG_NS, 'circle'); c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5'); svg.appendChild(c);
      statusSpan.appendChild(svg);
      statusSpan.appendChild(document.createTextNode(' '));
      const targetHint = item.redirect_target ? `Official Brand Redirect (Points to ${domain})` : 'Points to your own servers';
      statusSpan.appendChild(document.createTextNode(targetHint));
      right.appendChild(statusSpan);

      const checkBtn = document.createElement('a');
      checkBtn.href = `https://www.whois.com/whois/${encodeURIComponent(item.domain)}`;
      checkBtn.target = '_blank';
      checkBtn.rel = 'noopener noreferrer';
      checkBtn.className = 'pr-btn pr-btn-quiet pr-lookalike-btn';
      checkBtn.textContent = 'Verify WHOIS';
      right.appendChild(checkBtn);
    } else if (isLive && webStatus === 'active') {
      statusSpan.classList.add('pr-status-crit');
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 12 12'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10');
      svg.setAttribute('fill', 'var(--pr-crit)'); svg.setAttribute('aria-hidden', 'true');
      const poly = document.createElementNS(SVG_NS, 'polygon'); poly.setAttribute('points', '6,1 11,6 6,11 1,6'); svg.appendChild(poly);
      statusSpan.appendChild(svg);
      statusSpan.appendChild(document.createTextNode(' '));
      const codeText = item.http_code ? ` (HTTP ${item.http_code})` : '';
      statusSpan.appendChild(document.createTextNode(`Live Web Server${codeText} - Threat`));
      right.appendChild(statusSpan);

      const checkBtn = document.createElement('a');
      checkBtn.href = `https://www.whois.com/whois/${encodeURIComponent(item.domain)}`;
      checkBtn.target = '_blank';
      checkBtn.rel = 'noopener noreferrer';
      checkBtn.className = 'pr-btn pr-btn-quiet pr-lookalike-btn';
      checkBtn.textContent = 'Check ownership';
      right.appendChild(checkBtn);
    } else if (isLive) {
      statusSpan.classList.add('pr-status-med');
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 12 12'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10');
      svg.setAttribute('fill', 'var(--pr-med, var(--warning))'); svg.setAttribute('aria-hidden', 'true');
      const poly = document.createElementNS(SVG_NS, 'polygon'); poly.setAttribute('points', '6,1 11,6 6,11 1,6'); svg.appendChild(poly);
      statusSpan.appendChild(svg);
      statusSpan.appendChild(document.createTextNode(' '));
      statusSpan.appendChild(document.createTextNode('Resolves, no web server answered'));
      right.appendChild(statusSpan);

      const checkBtn = document.createElement('a');
      checkBtn.href = `https://www.whois.com/whois/${encodeURIComponent(item.domain)}`;
      checkBtn.target = '_blank';
      checkBtn.rel = 'noopener noreferrer';
      checkBtn.className = 'pr-btn pr-btn-quiet pr-lookalike-btn';
      checkBtn.textContent = 'Check ownership';
      right.appendChild(checkBtn);
    } else if (isUnk) {
      statusSpan.classList.add('pr-status-unavail');
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 12 12'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10');
      svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('stroke-width', '1.5');
      svg.setAttribute('stroke-dasharray', '2 2'); svg.setAttribute('aria-hidden', 'true');
      const c = document.createElementNS(SVG_NS, 'circle'); c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5'); svg.appendChild(c);
      statusSpan.appendChild(svg);
      statusSpan.appendChild(document.createTextNode(' '));
      statusSpan.appendChild(document.createTextNode("Couldn't be checked"));
      right.appendChild(statusSpan);
    } else {
      statusSpan.classList.add('pr-status-neutral');
      const svg = document.createElementNS(SVG_NS, 'svg');
      svg.setAttribute('viewBox', '0 0 12 12'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10');
      svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('stroke-width', '1.75');
      svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round'); svg.setAttribute('aria-hidden', 'true');
      const poly = document.createElementNS(SVG_NS, 'polyline'); poly.setAttribute('points', '2.5 6 5 8.5 9.5 3.5'); svg.appendChild(poly);
      statusSpan.appendChild(svg);
      statusSpan.appendChild(document.createTextNode(' '));
      statusSpan.appendChild(document.createTextNode('No DNS record found'));
      right.appendChild(statusSpan);
    }

    row.appendChild(right);
    listEl.appendChild(row);
  });
}

function renderEvidenceSubdomains(state) {
  const metaEl = document.getElementById('pr-meta-subdomains');
  const countEl = document.getElementById('pr-subdomains-count');
  const headerEl = document.getElementById('pr-subdomains-header');
  const pillsEl = document.getElementById('pr-subdomains-pills');
  const unavailEl = document.getElementById('pr-subdomains-unavail');
  if (!pillsEl) return;

  const subdomains = state.checks?.subdomains?.data || state.subdomains;
  const subStatus = state.checks?.subdomains?.status || state.subdomains?.status;

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isUnavail = subStatus === 'unavailable' || subStatus === 'error' || incomplete.some(s => s.includes('subdomain'));

  const subs = Array.isArray(subdomains?.subdomains) ? subdomains.subdomains : [];
  const total = subdomains?.count ?? subdomains?.total ?? subs.length;

  if (metaEl) {
    if (isUnavail) metaEl.textContent = "Couldn't be checked";
    else if (subStatus === 'ok' || subs.length > 0) metaEl.textContent = `${total} found`;
    else metaEl.textContent = '';
  }

  if (isUnavail) {
    if (headerEl) headerEl.style.display = 'none';
    if (pillsEl) pillsEl.style.display = 'none';
    if (unavailEl) unavailEl.style.display = 'flex';
    return;
  }

  if (headerEl) headerEl.style.display = 'flex';
  if (pillsEl) pillsEl.style.display = 'grid';
  if (unavailEl) unavailEl.style.display = 'none';

  if (subs.length === 0 && subStatus === 'ok') {
    if (countEl) countEl.textContent = 'No subdomains appear in public certificate logs.';
    if (metaEl) metaEl.textContent = 'None found';
    pillsEl.style.display = 'block';
    pillsEl.replaceChildren();
    const emptyMsg = document.createElement('div');
    emptyMsg.className = 'pr-subdomain-empty-note';
    emptyMsg.style.color = 'var(--pr-ink-3)';
    emptyMsg.style.fontSize = '13.5px';
    emptyMsg.style.padding = '8px 0';
    emptyMsg.textContent = 'No subdomains appear in public certificate logs.';
    pillsEl.appendChild(emptyMsg);
    return;
  }

  if (countEl) {
    countEl.textContent = `${total} found, showing ${Math.min(total, subs.length)}`;
  }

  pillsEl.replaceChildren();

  const ringedKeywords = [
    'staging', 'dev', 'test', 'uat', 'admin', 'vpn', 'internal',
    'corp', 'beta', 'sandbox', 'demo', 'qa', 'lab', 'bastion',
    'dev-api', 'db-prod', 'jira', 'gitlab', 'k8s', 'status', 'sso', 'billing'
  ];

  subs.forEach((hostname) => {
    const pill = document.createElement('a');
    pill.href = `https://${hostname}`;
    pill.target = '_blank';
    pill.rel = 'noopener noreferrer';
    pill.className = 'pr-subdomain-pill';
    pill.setAttribute('data-evidence-item', hostname);
    pill.title = `Visit https://${hostname} (opens in new tab)`;

    const subLabel = hostname.split('.')[0].toLowerCase();
    const isRinged = ringedKeywords.some(kw => subLabel === kw || subLabel.startsWith(kw + '-') || subLabel.endsWith('-' + kw) || subLabel.includes(kw));
    if (isRinged) {
      pill.classList.add('is-ringed');
    }

    // Favicon icon
    const iconSpan = document.createElement('span');
    iconSpan.className = 'pr-pill-favicon';
    iconSpan.appendChild(createGlobeSvg(14));
    pill.appendChild(iconSpan);

    const textSpan = document.createElement('span');
    textSpan.className = 'pr-pill-text';
    textSpan.textContent = hostname;
    pill.appendChild(textSpan);

    if (isRinged) {
      const reviewChip = document.createElement('span');
      reviewChip.className = 'pr-chip-review';
      reviewChip.textContent = 'Review';
      pill.appendChild(reviewChip);
    }

    pillsEl.appendChild(pill);
  });
}

function renderEvidenceSurface(state) {
  const metaEl = document.getElementById('pr-meta-surface');
  const contentEl = document.getElementById('pr-surface-content');
  if (!contentEl) return;

  const surface = state.checks?.surface?.data || state.surface;
  const surfStatus = state.checks?.surface?.status || state.surface?.status;

  const incomplete = (state.summary && Array.isArray(state.summary.incomplete)) ? state.summary.incomplete.map(s => String(s).toLowerCase()) : [];
  const isUnavail = surfStatus === 'unavailable' || surfStatus === 'error' || incomplete.some(s => s.includes('surface') || s.includes('public'));

  const emails = Array.isArray(surface?.emails) ? surface.emails : [];
  const socials = surface?.socials && typeof surface.socials === 'object' ? surface.socials : {};
  const socialEntries = Object.entries(socials);

  if (metaEl) {
    if (isUnavail) metaEl.textContent = "Couldn't be retrieved";
    else if (surface?.blocked) metaEl.textContent = "Blocked";
    else if (surfStatus === 'ok' || emails.length > 0 || socialEntries.length > 0) {
      const parts = [];
      if (emails.length > 0) parts.push(`${emails.length} email${emails.length === 1 ? '' : 's'}`);
      if (socialEntries.length > 0) parts.push(`${socialEntries.length} profile${socialEntries.length === 1 ? '' : 's'}`);
      metaEl.textContent = parts.length > 0 ? parts.join(' · ') : 'No public surface';
    } else {
      metaEl.textContent = '';
    }
  }

  contentEl.replaceChildren();

  if (isUnavail) {
    const unavailDiv = document.createElement('div');
    unavailDiv.className = 'pr-surface-note';
    unavailDiv.textContent = "Couldn't retrieve public website surface. A public service didn't respond in time. ";
    const retryBtn = document.createElement('button');
    retryBtn.type = 'button';
    retryBtn.className = 'pr-inline-retry-btn';
    retryBtn.textContent = 'Run again';
    retryBtn.onclick = handlePartialRetry;
    unavailDiv.appendChild(retryBtn);
    contentEl.appendChild(unavailDiv);
    return;
  }

  if (surface?.blocked) {
    const blockDiv = document.createElement('div');
    blockDiv.className = 'pr-surface-note';
    blockDiv.textContent = "The site blocked automated retrieval, so nothing can be concluded here.";
    contentEl.appendChild(blockDiv);
    return;
  }

  if (emails.length === 0 && socialEntries.length === 0) {
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'pr-surface-note';
    emptyDiv.textContent = "We didn't find emails or profiles on the pages we could retrieve.";
    contentEl.appendChild(emptyDiv);
    return;
  }

  // Published emails
  if (emails.length > 0) {
    const emailGroup = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'pr-surface-group-title';
    title.textContent = 'Published emails';
    emailGroup.appendChild(title);

    emails.forEach((email) => {
      const row = document.createElement('div');
      row.className = 'pr-surface-row';
      row.setAttribute('data-evidence-item', email);

      const left = document.createElement('div');
      left.className = 'pr-surface-left';
      const code = document.createElement('code');
      code.className = 'pr-mono';
      code.textContent = email;
      left.appendChild(code);
      row.appendChild(left);

      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'pr-btn pr-btn-quiet pr-copy-btn';
      copyBtn.textContent = 'Copy';
      copyBtn.onclick = function() { copyTextToClipboard(email, this); };
      row.appendChild(copyBtn);

      emailGroup.appendChild(row);
    });

    contentEl.appendChild(emailGroup);
  }

  // Social profiles
  if (socialEntries.length > 0) {
    const socialGroup = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'pr-surface-group-title';
    title.textContent = 'Social profiles';
    emailGroup = socialGroup;
    socialGroup.appendChild(title);

    socialEntries.forEach(([platform, rawUrl]) => {
      const safeUrl = sanitizeExternalUrl(rawUrl);
      if (!safeUrl) return;

      const row = document.createElement('div');
      row.className = 'pr-surface-row';
      row.setAttribute('data-evidence-item', platform);

      const left = document.createElement('div');
      left.className = 'pr-surface-left';

      const platSpan = document.createElement('span');
      platSpan.className = 'pr-surface-platform';
      platSpan.textContent = platform.charAt(0).toUpperCase() + platform.slice(1);
      left.appendChild(platSpan);

      const link = document.createElement('a');
      link.href = safeUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'pr-mono pr-surface-link';
      try {
        const u = new URL(safeUrl);
        link.textContent = u.hostname + u.pathname;
      } catch (e) {
        link.textContent = safeUrl;
      }
      left.appendChild(link);
      row.appendChild(left);

      socialGroup.appendChild(row);
    });

    contentEl.appendChild(socialGroup);
  }
}

function updateAccordionsDefaultOpen(state) {
  const lookalikes = state.checks?.lookalikes?.data || state.lookalikes;
  const ssl = state.checks?.tls?.data || state.ssl;
  const emailAuth = state.checks?.email_auth?.data || state.email_auth;

  const lookDetails = document.getElementById('pr-evidence-lookalikes');
  const domainDetails = document.getElementById('pr-evidence-domain');
  const emailDetails = document.getElementById('pr-evidence-email-auth');

  // Look-alike domains: opens automatically if any resolve
  if (lookDetails && !userManuallyToggledAccordions.has('lookalikes') && !autoOpenedAccordions.has('lookalikes')) {
    const details = Array.isArray(lookalikes?.details) ? lookalikes.details : [];
    const resolving = details.filter(d => d.state === 'resolves' || d.status === 'resolves' || d.is_live || d.resolves).length || lookalikes?.live_count || 0;
    if (resolving >= 1) {
      lookDetails.open = true;
      autoOpenedAccordions.add('lookalikes');
    }
  }

  // Domain & Certificate: opens automatically if TLS is invalid
  if (domainDetails && !userManuallyToggledAccordions.has('domain') && !autoOpenedAccordions.has('domain')) {
    if (ssl && ssl.valid === false) {
      domainDetails.open = true;
      autoOpenedAccordions.add('domain');
    }
  }

  // Email authentication: opens automatically when DMARC is missing or p=none
  if (emailDetails && !userManuallyToggledAccordions.has('email_auth') && !autoOpenedAccordions.has('email_auth')) {
    const dmarcStatus = emailAuth?.dmarc?.status;
    const isMissingOrNone = dmarcStatus === 'missing' || dmarcStatus === 'none' || (emailAuth && !emailAuth.dmarc?.record);
    if (emailAuth && isMissingOrNone) {
      emailDetails.open = true;
      autoOpenedAccordions.add('email_auth');
    }
  }
}

function renderEvidenceSection(state) {
  renderEvidenceDomainCert(state);
  renderEvidenceEmailAuth(state);
  renderEvidenceLookalikes(state);
  renderEvidenceSubdomains(state);
  renderEvidenceSurface(state);
  updateAccordionsDefaultOpen(state);
}

function renderAnalystNote(state) {
  const sectionEl = document.getElementById('pr-analyst-section');
  const quoteEl = document.getElementById('pr-analyst-quote');
  const pendingEl = document.getElementById('pr-analyst-pending');
  if (!sectionEl || !quoteEl) return;

  const hasAiNote = state.ai && state.ai.ai_analysis && (state.ai.path_used === 'heuristic+ai' || state.summary?.path_used === 'heuristic+ai');

  if (hasAiNote) {
    if (pendingEl) pendingEl.style.display = 'none';
    sectionEl.style.display = 'block';
    quoteEl.textContent = state.ai.ai_analysis;
  } else if (state.phase === 'running' && state.summary && !state.ai) {
    if (pendingEl) pendingEl.style.display = 'block';
    sectionEl.style.display = 'none';
  } else {
    if (pendingEl) pendingEl.style.display = 'none';
    sectionEl.style.display = 'none';
  }
}

function handleCheckRowClick(checkId) {
  let targetSection = null;
  if (checkId === 'tls' || checkId === 'domain') {
    targetSection = document.getElementById('pr-evidence-domain');
  } else if (checkId === 'email_auth') {
    targetSection = document.getElementById('pr-evidence-email-auth');
  } else if (checkId === 'lookalikes') {
    targetSection = document.getElementById('pr-evidence-lookalikes');
  } else if (checkId === 'subdomains') {
    targetSection = document.getElementById('pr-evidence-subdomains');
  } else if (checkId === 'surface') {
    targetSection = document.getElementById('pr-evidence-surface');
  }

  if (!targetSection) {
    targetSection = document.querySelector(`[data-check-section="${checkId}"]`) ||
                    document.getElementById(`pr-evidence-${checkId}`) ||
                    document.getElementById('pr-evidence');
  }

  if (targetSection) {
    if (targetSection.tagName === 'DETAILS') {
      targetSection.open = true;
    } else {
      const parent = targetSection.closest('details.pr-accordion');
      if (parent) parent.open = true;
    }
    targetSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    targetSection.style.transition = 'background-color 300ms ease';
    targetSection.style.backgroundColor = 'rgba(14, 165, 233, 0.08)';
    setTimeout(() => {
      targetSection.style.backgroundColor = '';
    }, 1200);
  }
}

// ════════════════════════════════════════════════════════════════
// PART 8: CONDENSING HEADER, ACTIONS & PRINT / PDF ENGINE
// ════════════════════════════════════════════════════════════════

let condensedObserver = null;
let activeActionMenuTrigger = null;

function updateNavbarPosition() {
  const navbar = document.querySelector('.navbar') || document.querySelector('header.navbar');
  const condensedBar = document.getElementById('pr-condensed-bar');
  if (condensedBar) {
    const navBottom = navbar ? Math.max(0, navbar.getBoundingClientRect().bottom) : 72;
    condensedBar.style.top = `${navBottom}px`;
    document.documentElement.style.setProperty('--pr-nav-height', `${navBottom}px`);
  }
}

function checkVerdictVisibility() {
  const verdictH1 = document.getElementById('pr-verdict-heuristic') || document.getElementById('pr-verdict-stack') || document.getElementById('pr-verdict-section');
  const condensedBar = document.getElementById('pr-condensed-bar');
  if (!verdictH1 || !condensedBar) return;
  const navbar = document.querySelector('.navbar') || document.querySelector('header.navbar');
  const navBottom = navbar ? Math.max(0, navbar.getBoundingClientRect().bottom) : 72;
  const verdictRect = verdictH1.getBoundingClientRect();
  
  // If the bottom of the verdict heading is above the navbar or scrolled out of view
  if (verdictRect.bottom <= navBottom + 30) {
    condensedBar.classList.add('is-visible');
  } else {
    condensedBar.classList.remove('is-visible');
    closeActionMenu();
  }
}

function initCondensedHeader() {
  const condensedBar = document.getElementById('pr-condensed-bar');
  const verdictH1 = document.getElementById('pr-verdict-heuristic') || document.getElementById('pr-verdict-stack') || document.getElementById('pr-verdict-section');
  if (!condensedBar || !verdictH1) return;

  updateNavbarPosition();
  window.addEventListener('resize', () => {
    updateNavbarPosition();
    checkVerdictVisibility();
  });
  window.addEventListener('scroll', () => {
    updateNavbarPosition();
    checkVerdictVisibility();
  }, { passive: true });

  if (window.IntersectionObserver) {
    if (condensedObserver) condensedObserver.disconnect();
    
    condensedObserver = new IntersectionObserver((entries) => {
      entries.forEach(() => {
        checkVerdictVisibility();
      });
    }, {
      threshold: [0, 0.25, 0.5, 0.75, 1]
    });

    condensedObserver.observe(verdictH1);
  }

  checkVerdictVisibility();
}

function renderCondensedHeader(state) {
  const bar = document.getElementById('pr-condensed-bar');
  if (!bar) return;

  const isNotEnoughData = Boolean(
    state.summary && (state.summary.posture === 'Not enough data' || state.summary.exposure_score === null)
  );

  const domain = state.domain || 'acme.example';
  const score = isNotEnoughData ? '—' : (state.summary?.exposure_score ?? (typeof state.score === 'number' ? state.score : '—'));
  const posture = isNotEnoughData ? 'Not enough data' : (state.summary?.posture ?? (state.posture || 'Pending'));

  // Domain
  const domEl = document.getElementById('pr-condensed-domain');
  if (domEl) domEl.textContent = domain;

  // Favicon
  const favSlot = document.getElementById('pr-condensed-fav');
  if (favSlot) {
    const cleanDom = cleanDomainInput(domain);
    favSlot.replaceChildren();
    const img = document.createElement('img');
    // third-party favicon request removed for privacy (A4)
    img.alt = '';
    img.onerror = () => {
      favSlot.replaceChildren();
      const letter = document.createElement('div');
      letter.className = 'pr-fav-letter';
      letter.textContent = cleanDom ? cleanDom.charAt(0).toUpperCase() : '?';
      favSlot.appendChild(letter);
    };
    favSlot.appendChild(img);
  }

  // Score
  const scoreEl = document.getElementById('pr-condensed-score');
  if (scoreEl) scoreEl.textContent = score;

  // Posture Word
  const postureWordEl = document.getElementById('pr-condensed-posture-word');
  if (postureWordEl) postureWordEl.textContent = posture;

  // Posture Icon
  const iconSlot = document.getElementById('pr-condensed-posture-icon');
  if (iconSlot) {
    iconSlot.replaceChildren();
    const p = String(posture).toLowerCase();
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 12 12');
    svg.setAttribute('width', '12');
    svg.setAttribute('height', '12');
    svg.setAttribute('aria-hidden', 'true');

    if (p.includes('crit')) {
      const poly = document.createElementNS(SVG_NS, 'polygon');
      poly.setAttribute('points', '6,1 11,11 1,11');
      poly.setAttribute('fill', 'var(--pr-crit)');
      svg.appendChild(poly);
      bar.style.setProperty('--pr-tone', 'var(--pr-crit)');
    } else if (p.includes('elev')) {
      const poly = document.createElementNS(SVG_NS, 'polygon');
      poly.setAttribute('points', '6,1 11,11 1,11');
      poly.setAttribute('fill', 'var(--pr-high)');
      svg.appendChild(poly);
      bar.style.setProperty('--pr-tone', 'var(--pr-high)');
    } else if (p.includes('mod')) {
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5');
      c.setAttribute('fill', 'var(--pr-mod)');
      svg.appendChild(c);
      bar.style.setProperty('--pr-tone', 'var(--pr-mod)');
    } else if (p.includes('low')) {
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5');
      c.setAttribute('fill', 'none');
      c.setAttribute('stroke', 'var(--pr-low)');
      c.setAttribute('stroke-width', '1.8');
      svg.appendChild(c);
      bar.style.setProperty('--pr-tone', 'var(--pr-low)');
    } else {
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('cx', '6'); c.setAttribute('cy', '6'); c.setAttribute('r', '4.5');
      c.setAttribute('fill', 'none');
      c.setAttribute('stroke', 'var(--pr-ink-3)');
      c.setAttribute('stroke-width', '1.8');
      svg.appendChild(c);
      bar.style.setProperty('--pr-tone', 'var(--pr-ink-3)');
    }
    iconSlot.appendChild(svg);
  }
}

function renderMetaActions(state) {
  const isSample = state.mode === 'sample' || Boolean(state.sample);
  const shareBtnDesk = document.getElementById('pr-action-share');
  const shareBtnCond = document.getElementById('pr-condensed-share');
  const shareBtnMenu = document.getElementById('pr-menu-share');

  [shareBtnDesk, shareBtnCond, shareBtnMenu].forEach(btn => {
    if (!btn) return;
    if (isSample) {
      btn.setAttribute('disabled', 'true');
      btn.setAttribute('title', 'Run a live audit first to share this report');
      btn.style.opacity = '0.45';
      btn.style.cursor = 'not-allowed';
    } else {
      btn.removeAttribute('disabled');
      btn.setAttribute('title', 'Copy shareable audit link');
      btn.style.opacity = '1';
      btn.style.cursor = 'pointer';
    }
  });

  // Update print metadata targets in DOM
  const printDomain = document.getElementById('pr-print-domain');
  const printDate = document.getElementById('pr-print-date');
  const printId = document.getElementById('pr-print-id');
  const printFooterId = document.getElementById('pr-print-footer-id');
  const currentDomain = state.domain || 'acme.example';
  const currentDate = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const auditId = state.summary?.investigation_id || state.id || `audit-${currentDomain.replace(/[^a-zA-Z0-9]/g, '-')}`;

  if (printDomain) printDomain.textContent = currentDomain;
  if (printDate) printDate.textContent = currentDate;
  if (printId) printId.textContent = auditId;
  if (printFooterId) printFooterId.textContent = auditId;
}

function handleShareLink() {
  if (state.mode === 'sample' || Boolean(state.sample)) {
    showDemoToast('Run a live audit first to share this report.');
    return;
  }
  const cleanDom = cleanDomainInput(state.domain || '');
  const shareUrl = `${window.location.origin}/exposure-report?domain=${encodeURIComponent(cleanDom)}`;
  copyTextToClipboard(shareUrl);
  showDemoToast('Link copied');
}

function handleDownloadReport() {
  const currentDomain = state.domain || 'acme.example';
  const dateStr = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const previousTitle = document.title;
  
  // Set explicit print title: "PhishRecon report, <domain>, <date>"
  document.title = `PhishRecon report, ${currentDomain}, ${dateStr}`;

  // Ensure score and marker are locked in final static state for print layout
  if (state.summary && typeof state.summary.exposure_score === 'number') {
    const scoreNumEl = document.getElementById('pr-score-numeral');
    const markerEl = document.getElementById('pr-track-marker');
    const chipEl = document.getElementById('pr-track-chip');
    if (scoreNumEl) scoreNumEl.textContent = state.summary.exposure_score;
    if (markerEl) {
      markerEl.style.display = 'block';
      markerEl.style.left = `${state.summary.exposure_score}%`;
    }
    if (chipEl) chipEl.textContent = state.summary.exposure_score;
  }

  // Open all details accordions for complete print capture
  const details = document.querySelectorAll('details.pr-accordion');
  const previousOpen = Array.from(details).map(d => d.open);
  details.forEach(d => { d.open = true; });

  // Make sure print metadata elements are refreshed
  renderMetaActions(state);

  // Invoke print
  window.print();

  // Restore previous title and details open states afterwards
  const restore = () => {
    document.title = previousTitle;
    details.forEach((d, idx) => { d.open = previousOpen[idx]; });
    window.removeEventListener('afterprint', restore);
  };
  window.addEventListener('afterprint', restore);
  setTimeout(restore, 1500);
}

function handleCopySummary() {
  const currentDomain = state.domain || 'acme.example';
  const dateStr = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const score = state.summary?.exposure_score ?? (typeof state.score === 'number' ? state.score : '—');
  const posture = state.summary?.posture ?? (state.posture || 'Pending');
  
  // Verdict sentence
  const verdictEl = document.getElementById('pr-verdict-ai') || document.getElementById('pr-verdict-heuristic');
  const verdict = state.ai?.executive_verdict || state.summary?.executive_verdict || (verdictEl ? verdictEl.textContent.trim() : '');

  // Findings
  const findings = generateFindings(state);
  const findingsList = findings.map(f => `- ${f.severity}: ${f.title.replace(/<[^>]+>/g, '')}`).join('\n');

  const summaryText = [
    `Attack surface audit: ${currentDomain}`,
    `Date: ${dateStr}`,
    `Score: ${score}/100 (${posture})`,
    '',
    verdict,
    '',
    'Start here:',
    findingsList || '- No major risks identified.'
  ].filter(line => line !== undefined).join('\n');

  copyTextToClipboard(summaryText);
  showDemoToast('Summary copied');
}

function handleCopyRawData() {
  const rawObj = {
    domain: state.domain || 'acme.example',
    investigation_id: state.summary?.investigation_id || state.id || 'EX-AUDIT',
    exposure_score: state.summary?.exposure_score ?? state.score,
    posture: state.summary?.posture ?? state.posture,
    timestamp: state.timestamp || new Date().toISOString(),
    checks: state.checks,
    summary: state.summary,
    ai_analysis: state.ai
  };
  copyTextToClipboard(JSON.stringify(rawObj, null, 2));
  showDemoToast('Raw JSON copied');
}

function handleNewAudit() {
  closeActionMenu(false);
  const domainInput = document.getElementById('pr-domain-input');
  if (domainInput) {
    domainInput.value = '';
    updateFavicon('');
    clearValidationError();
    setTimeout(() => {
      domainInput.focus();
    }, 50);
  }
  run('acme.example', { sample: true, variant: 'default', instant: true });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleActionMenu(triggerEl, context) {
  const menu = document.getElementById('pr-actions-menu');
  if (!menu) return;

  if (menu.style.display === 'block' && activeActionMenuTrigger === triggerEl) {
    closeActionMenu(true);
    return;
  }

  activeActionMenuTrigger = triggerEl;
  triggerEl.setAttribute('aria-expanded', 'true');

  const rect = triggerEl.getBoundingClientRect();
  menu.style.display = 'block';

  // Position anchored below trigger
  const menuWidth = 240;
  let left = rect.right - menuWidth;
  if (left < 10) left = 10;
  let top = rect.bottom + 6;

  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;

  // Focus the first item
  const firstItem = menu.querySelector('.pr-menu-item:not([disabled])');
  if (firstItem) firstItem.focus();
}

function closeActionMenu(restoreFocus = true) {
  const menu = document.getElementById('pr-actions-menu');
  if (!menu) return;
  menu.style.display = 'none';
  if (activeActionMenuTrigger) {
    activeActionMenuTrigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) {
      activeActionMenuTrigger.focus();
    }
    activeActionMenuTrigger = null;
  }
}

// Menu keyboard navigation & outside dismiss
document.addEventListener('pointerdown', (e) => {
  const menu = document.getElementById('pr-actions-menu');
  if (menu && menu.style.display === 'block') {
    if (!menu.contains(e.target) && (!activeActionMenuTrigger || !activeActionMenuTrigger.contains(e.target))) {
      closeActionMenu(true);
    }
  }
});

document.addEventListener('keydown', (e) => {
  const menu = document.getElementById('pr-actions-menu');
  if (!menu || menu.style.display !== 'block') return;

  const items = Array.from(menu.querySelectorAll('.pr-menu-item:not([disabled])'));
  const activeIdx = items.indexOf(document.activeElement);

  if (e.key === 'Escape') {
    e.preventDefault();
    closeActionMenu(true);
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    const nextIdx = activeIdx >= 0 ? (activeIdx + 1) % items.length : 0;
    items[nextIdx]?.focus();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    const prevIdx = activeIdx > 0 ? activeIdx - 1 : items.length - 1;
    items[prevIdx]?.focus();
  } else if (e.key === 'Tab') {
    closeActionMenu(true);
  }
});

// ── 6. Debug Panel Controller (Visible only with ?debug=1) ─────
function initDebugPanel() {
  const params = new URLSearchParams(window.location.search);
  const isDebug = params.get('debug') === '1';
  if (!isDebug) return;

  // Expose window.__pr ONLY in debug mode
  window.__pr = {
    get state() { return state; },
    dispatch,
    run: (d, o) => run(d, o),
    history: phishReconHistory
  };

  const panel = document.createElement('aside');
  panel.id = 'pr-debug-panel';
  panel.className = 'pr-debug-panel';
  panel.setAttribute('aria-label', 'PhishRecon Engine Debug Panel');

  // Header
  const header = document.createElement('div');
  header.className = 'pr-debug-header';
  const title = document.createElement('span');
  title.textContent = 'Engine Debug (?debug=1)';
  
  const toggleBtn = document.createElement('button');
  toggleBtn.type = 'button';
  toggleBtn.className = 'pr-debug-btn';
  toggleBtn.textContent = 'Minimize';
  let isMinimized = false;
  toggleBtn.onclick = () => {
    isMinimized = !isMinimized;
    body.style.display = isMinimized ? 'none' : 'block';
    controls.style.display = isMinimized ? 'none' : 'flex';
    toggleBtn.textContent = isMinimized ? 'Expand' : 'Minimize';
  };
  header.appendChild(title);
  header.appendChild(toggleBtn);
  panel.appendChild(header);

  // Controls
  const controls = document.createElement('div');
  controls.className = 'pr-debug-controls';

  function createBtn(label, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pr-debug-btn';
    btn.textContent = label;
    btn.onclick = onClick;
    return btn;
  }

  controls.appendChild(createBtn('Sample: Default', () => run('acme.example', { sample: true, variant: 'default' })));
  controls.appendChild(createBtn('Sample: Partial', () => run('acme.example', { sample: true, variant: 'partial' })));
  controls.appendChild(createBtn('Sample: Low', () => run('acme.example', { sample: true, variant: 'low' })));
  controls.appendChild(createBtn('Sample: Critical', () => run('acme.example', { sample: true, variant: 'critical' })));
  controls.appendChild(createBtn('Sample: No Mail', () => run('acme-assets.example', { sample: true, variant: 'no_mail' })));
  controls.appendChild(createBtn('Abort', () => abortInFlight()));

  // Domain live test input
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'live domain';
  input.style.cssText = 'height: 22px; width: 110px; padding: 0 6px; font-family: var(--font-mono); font-size: 10px; background: var(--pr-paper); color: var(--pr-ink); border: 1px solid var(--pr-line); border-radius: 4px;';
  input.value = 'example.com';
  controls.appendChild(input);

  controls.appendChild(createBtn('Run Live', () => {
    if (input.value) run(input.value, { sample: false });
  }));

  panel.appendChild(controls);

  // Body with pre
  const body = document.createElement('div');
  body.className = 'pr-debug-body';
  const pre = document.createElement('pre');
  pre.id = 'pr-debug-json';
  pre.className = 'pr-debug-pre';
  pre.textContent = JSON.stringify(state, null, 2);
  body.appendChild(pre);
  panel.appendChild(body);

  document.body.appendChild(panel);
}

// ── 7. Toast & Preview Helper Utilities ────────────────────────
let toastTimer = null;

function showDemoToast(msg) {
  let el = document.getElementById('pr-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'pr-toast';
    el.className = 'pr-toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('is-active');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove('is-active');
  }, 2200);
}

function setPosturePreview(posture) {
  const sheet = document.getElementById('pr-sheet');
  if (!sheet) return;
  sheet.setAttribute('data-posture', posture);
  showDemoToast('Posture preview: ' + posture);
}

// ── 8. URL Bootstrapping & Idle (Sample) Engine (Section 3 & 6) ─

function initStaticActionListeners() {
  document.getElementById('pr-condensed-share')?.addEventListener('click', handleShareLink);
  document.getElementById('pr-condensed-download')?.addEventListener('click', handleDownloadReport);
  document.getElementById('pr-condensed-summary')?.addEventListener('click', handleCopySummary);
  const condOver = document.getElementById('pr-condensed-overflow-btn');
  if (condOver) {
    condOver.addEventListener('click', function() { toggleActionMenu(this, 'condensed'); });
  }

  const cmdForm = document.getElementById('pr-command-form');
  if (cmdForm) {
    cmdForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleFormSubmit();
    });
  }

  document.getElementById('pr-stop-btn')?.addEventListener('click', handleStopClick);
  document.getElementById('pr-see-sample-btn')?.addEventListener('click', handleReplaySampleClick);

  document.getElementById('pr-action-share')?.addEventListener('click', handleShareLink);
  document.getElementById('pr-action-download')?.addEventListener('click', handleDownloadReport);
  document.getElementById('pr-action-summary')?.addEventListener('click', handleCopySummary);
  const sheetOver = document.getElementById('pr-sheet-overflow-btn');
  if (sheetOver) {
    sheetOver.addEventListener('click', function() { toggleActionMenu(this, 'sheet'); });
  }

  document.getElementById('pr-partial-retry-btn')?.addEventListener('click', handlePartialRetry);
  const explainerBtn = document.getElementById('pr-score-explainer-btn');
  if (explainerBtn) {
    explainerBtn.addEventListener('click', function() { handleExplainScoreClick(this); });
  }
  document.getElementById('pr-findings-toggle-btn')?.addEventListener('click', toggleFindingsExpand);
  const subCopy = document.getElementById('pr-subdomains-copy-btn');
  if (subCopy) {
    subCopy.addEventListener('click', function() { copyAllSubdomains(this); });
  }
  document.getElementById('pr-subdomains-retry-btn')?.addEventListener('click', handlePartialRetry);
  document.getElementById('pr-analyst-score-link')?.addEventListener('click', () => toggleScorePopover(true));

  document.getElementById('pr-menu-share')?.addEventListener('click', () => { handleShareLink(); closeActionMenu(); });
  document.getElementById('pr-menu-download')?.addEventListener('click', () => { handleDownloadReport(); closeActionMenu(); });
  document.getElementById('pr-menu-summary')?.addEventListener('click', () => { handleCopySummary(); closeActionMenu(); });
  document.getElementById('pr-menu-raw')?.addEventListener('click', () => { handleCopyRawData(); closeActionMenu(); });
  document.getElementById('pr-menu-new')?.addEventListener('click', () => { handleNewAudit(); closeActionMenu(); });
}

document.addEventListener('DOMContentLoaded', () => {
  initStaticActionListeners();
  initDebugPanel();
  initAccordionListeners();
  initCondensedHeader();

  // ?clean=1 support: hides command bar and sample notice for clean screenshots
  const params = new URLSearchParams(window.location.search);
  if (params.get('clean') === '1') {
    document.querySelector('.pr-page')?.classList.add('pr-clean-mode');
  }

  const domainInput = document.getElementById('pr-domain-input');

  // Input & keydown events: clears validation & updates favicon as soon as user edits
  if (domainInput) {
    const handleEdit = () => {
      clearValidationError();
      if (state.error && state.error.kind === 'validation') {
        state.error = null;
      }
      updateFavicon(domainInput.value);
    };

    domainInput.addEventListener('input', handleEdit);
    domainInput.addEventListener('keydown', (e) => {
      if (e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete') {
        clearValidationError();
        if (state.error && state.error.kind === 'validation') {
          state.error = null;
        }
      }
    });

    // Paste event: cleans URLs and emails automatically
    domainInput.addEventListener('paste', (e) => {
      const pasted = (e.clipboardData || window.clipboardData)?.getData('text');
      if (pasted) {
        e.preventDefault();
        const cleaned = cleanDomainInput(pasted);
        domainInput.value = cleaned;
        updateFavicon(cleaned);
        clearValidationError();
      }
    });
  }

  // Global keyboard shortcuts: "/" focuses input; "Escape" clears input or stops running audit
  document.addEventListener('keydown', (e) => {
    if (e.key === '/') {
      const active = document.activeElement;
      const isInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable);
      if (!isInput && domainInput) {
        e.preventDefault();
        domainInput.focus();
        domainInput.select();
      }
    } else if (e.key === 'Escape') {
      if (state.phase === 'running') {
        abortInFlight();
      } else if (document.activeElement === domainInput) {
        domainInput.value = '';
        clearValidationError();
        updateFavicon('');
      }
    }
  });

  // URL Bootstrapping & Idle Sample State Logic (Section 3 & 6)
  const sampleVariant = getSampleVariantFromUrl();
  const domainParam = params.get('domain');
  const autorunEl = document.querySelector('[data-autorun="1"]');
  const isAutorun = Boolean(autorunEl) || params.get('autorun') === '1';

  let sampleAlreadyPlayed = false;
  try {
    sampleAlreadyPlayed = sessionStorage.getItem('phishrecon:sample_played') === '1';
  } catch (e) {}

  if (isAutorun && domainParam && DOMAIN_VALIDATION_REGEX.test(cleanDomainInput(domainParam))) {
    const cleanDom = cleanDomainInput(domainParam);
    if (domainInput) domainInput.value = cleanDom;
    updateFavicon(cleanDom);
    run(cleanDom, { sample: false });
  } else if (sampleVariant !== null) {
    const demoDomain = sampleVariant === 'no_mail' ? 'acme-assets.example' : 'acme.example';
    if (domainInput) domainInput.value = demoDomain;
    updateFavicon(demoDomain);
    run(demoDomain, { sample: true, variant: sampleVariant, instant: false });
  } else {
    // Bare visit: automatic product demo sample
    // First visit in session plays timeline; later visits in same session render instant sample
    try {
      sessionStorage.setItem('phishrecon:sample_played', '1');
    } catch (e) {}

    if (domainInput) domainInput.value = 'acme.example';
    updateFavicon('acme.example');
    run('acme.example', {
      sample: true,
      variant: 'default',
      instant: sampleAlreadyPlayed
    });
  }

  // Expose engine controls for testing & debug
  window.dispatch = dispatch;
  window.render = render;
  window.resetState = resetState;
  window.abortInFlight = abortInFlight;
  window.state = state;
  window.phishreconState = state;
  window.run = run;
  window.handleReplaySampleClick = handleReplaySampleClick;

  // Lure Tour Finding Pulse: sequential 600ms pulse per finding using amber token
  window.lurePulseStartHereFindings = function() {
    const rows = document.querySelectorAll('#pr-findings-list .pr-finding-row');
    if (!rows || rows.length === 0) return;
    rows.forEach((row, idx) => {
      setTimeout(() => {
        let bulb = row.querySelector('.pr-lure-pulse-bulb');
        if (!bulb) {
          bulb = document.createElement('span');
          bulb.className = 'pr-lure-pulse-bulb';
          bulb.setAttribute('aria-hidden', 'true');
          const marker = row.querySelector('.pr-finding-marker');
          if (marker) {
            marker.appendChild(bulb);
          } else {
            row.prepend(bulb);
          }
        }
        bulb.classList.remove('is-pulsing');
        void bulb.offsetWidth;
        bulb.classList.add('is-pulsing');
        setTimeout(() => {
          bulb.classList.remove('is-pulsing');
        }, 650);
      }, idx * 700);
    });
  };

});
