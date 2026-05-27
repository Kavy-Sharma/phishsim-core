import os

claude_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PhishSim AI - Agentic Phishing Simulator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #05070f;
  --bg2: #080c1a;
  --bg3: #0d1226;
  --surface: rgba(255,255,255,0.04);
  --surface2: rgba(255,255,255,0.07);
  --border: rgba(255,255,255,0.08);
  --border2: rgba(99,179,237,0.25);
  --cyan: #38bdf8;
  --cyan2: #0ea5e9;
  --blue: #6366f1;
  --blue2: #818cf8;
  --white: #f0f4ff;
  --muted: #8892b0;
  --danger: #f87171;
  --success: #34d399;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Space Grotesk', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--white);
  overflow-x: hidden;
}

/* ── NOISE OVERLAY ── */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 1;
  opacity: 0.4;
}

/* ── GRID BACKGROUND ── */
.grid-bg {
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(56,189,248,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56,189,248,0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
  z-index: 0;
}

/* ── FLASH MESSAGES ── */
.flash-container {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  width: 90%;
  max-width: 600px;
}
.flash-message {
  background: rgba(5, 7, 15, 0.9);
  border: 1px solid var(--cyan);
  color: var(--white);
  padding: 12px 20px;
  border-radius: 8px;
  margin-bottom: 10px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  font-size: 0.9rem;
  text-align: center;
}

/* ── NAVBAR ── */
nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  padding: 20px 5%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.3s, backdrop-filter 0.3s, border-bottom 0.3s;
}
nav.scrolled {
  background: rgba(5,7,15,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
.nav-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--white);
}
.nav-logo svg { color: var(--cyan); }
.nav-logo span { color: var(--cyan); }
.nav-links { display: flex; align-items: center; gap: 32px; }
.nav-links a {
  color: var(--muted);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
  letter-spacing: 0.02em;
}
.nav-links a:hover { color: var(--white); }
.btn-nav {
  background: var(--blue);
  color: white;
  border: none;
  padding: 9px 22px;
  border-radius: 8px;
  font-family: var(--sans);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.2s, transform 0.15s;
  letter-spacing: 0.03em;
}
.btn-nav:hover { background: var(--blue2); transform: translateY(-1px); }

/* ── HERO ── */
#hero {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
  gap: 0;
  padding: 120px 5% 80px;
  position: relative;
  z-index: 2;
}

/* Left col */
.hero-left { padding-right: 5%; }

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(56,189,248,0.08);
  border: 1px solid rgba(56,189,248,0.2);
  border-radius: 100px;
  padding: 6px 14px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--cyan);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 28px;
}
.hero-eyebrow::before {
  content: '';
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--cyan);
  animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}

.hero-h1 {
  font-size: clamp(2.4rem, 4.5vw, 3.8rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-bottom: 20px;
}
.hero-h1 em {
  font-style: normal;
  background: linear-gradient(135deg, var(--cyan) 0%, var(--blue2) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-sub {
  font-size: 1rem;
  color: var(--muted);
  line-height: 1.7;
  max-width: 440px;
  margin-bottom: 36px;
}

.hero-actions { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: linear-gradient(135deg, var(--cyan2), var(--blue));
  color: white;
  padding: 13px 28px;
  border-radius: 10px;
  font-family: var(--sans);
  font-size: 0.92rem;
  font-weight: 600;
  border: none;
  cursor: pointer;
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}
.btn-primary::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, white, transparent);
  opacity: 0;
  transition: opacity 0.2s;
}
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(14,165,233,0.4); }
.btn-primary:hover::after { opacity: 0.1; }

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  background: none;
  border: 1px solid var(--border);
  padding: 13px 24px;
  border-radius: 10px;
  font-family: var(--sans);
  font-size: 0.92rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s, border-color 0.2s, transform 0.2s;
}
.btn-ghost:hover { color: var(--white); border-color: rgba(255,255,255,0.2); transform: translateY(-2px); }

.hero-trust {
  margin-top: 36px;
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}
.trust-item svg { color: var(--success); flex-shrink: 0; }

/* Right col — terminal */
.hero-right { position: relative; }

.terminal-wrapper {
  background: #0a0e1a;
  border: 1px solid rgba(56,189,248,0.2);
  border-radius: 14px;
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(56,189,248,0.05),
    0 20px 60px rgba(0,0,0,0.6),
    0 0 80px rgba(56,189,248,0.06);
  position: relative;
  transform: perspective(1000px) rotateY(-5deg) rotateX(2deg);
  transition: transform 0.4s ease;
}

.terminal-wrapper:hover {
  transform: perspective(1000px) rotateY(0deg) rotateX(0deg);
}

.terminal-wrapper::before {
  content: '';
  position: absolute;
  top: -1px; left: 10%; right: 10%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--cyan), transparent);
}

.terminal-bar {
  background: #111827;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.t-dots { display: flex; gap: 6px; }
.t-dot {
  width: 11px; height: 11px;
  border-radius: 50%;
}
.t-dot.red { background: #ff5f57; }
.t-dot.yellow { background: #ffbd2e; }
.t-dot.green { background: #28c840; }

.t-title {
  flex: 1;
  text-align: center;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--muted);
}
.t-live {
  display: flex;
  align-items: center;
  gap: 5px;
  background: rgba(56,189,248,0.1);
  border: 1px solid rgba(56,189,248,0.3);
  border-radius: 100px;
  padding: 2px 9px;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--cyan);
  letter-spacing: 0.06em;
}
.t-live::before {
  content: '';
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--cyan);
  animation: pulse-dot 1.5s infinite;
}

.terminal-body {
  padding: 20px;
  font-family: var(--mono);
  font-size: 0.78rem;
  line-height: 1.8;
  min-height: 320px;
  max-height: 400px;
  overflow-y: auto;
}
.terminal-body::-webkit-scrollbar { width: 4px; }
.terminal-body::-webkit-scrollbar-track { background: transparent; }
.terminal-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.t-logo-area {
  text-align: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.t-logo-area img { width: 56px; opacity: 0.9; }
.t-system-name {
  font-size: 0.72rem;
  color: var(--cyan);
  letter-spacing: 0.2em;
  font-weight: 700;
  margin-top: 8px;
}
.t-system-sub {
  font-size: 0.6rem;
  color: var(--muted);
  letter-spacing: 0.1em;
  margin-top: 2px;
}

.t-line { display: block; }
.t-ok { color: var(--success); }
.t-passive { color: #facc15; }
.t-info { color: var(--muted); }
.t-ready { color: var(--success); margin-top: 4px; }
.t-prompt { color: var(--cyan); }
.t-output { color: #e2e8f0; }
.t-error { color: var(--danger); }
.t-cmd { color: #fbbf24; }

.terminal-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: rgba(0,0,0,0.3);
}
.terminal-input-row span {
  font-family: var(--mono);
  font-size: 0.78rem;
  color: var(--cyan);
  white-space: nowrap;
}
.terminal-input-row input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: #e2e8f0;
  font-family: var(--mono);
  font-size: 0.78rem;
  caret-color: var(--cyan);
}

/* ── TICKER REPLACEMENT: 3-col stats ── */
.hero-stats {
  position: relative;
  z-index: 2;
  padding: 32px 5%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  background: rgba(5,7,15,0.6);
  backdrop-filter: blur(10px);
}
.hero-stat {
  padding: 24px 32px;
  border-right: 1px solid var(--border);
  text-align: center;
}
.hero-stat:last-child { border-right: none; }
.hero-stat-number {
  font-size: 2.4rem;
  font-weight: 700;
  color: var(--cyan);
  letter-spacing: -0.04em;
  line-height: 1;
  margin-bottom: 6px;
}
.hero-stat-label {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
  letter-spacing: 0.03em;
}

/* ── SECTION COMMON ── */
section { position: relative; z-index: 2; }
.section-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 16px;
}
.section-eyebrow::before, .section-eyebrow::after {
  content: '';
  display: block;
  height: 1px;
  width: 30px;
  background: var(--cyan);
  opacity: 0.4;
}
.section-title {
  font-size: clamp(1.8rem, 3vw, 2.8rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin-bottom: 16px;
}
.section-sub {
  font-size: 0.97rem;
  color: var(--muted);
  line-height: 1.7;
  max-width: 520px;
}
.text-center { text-align: center; }
.text-center .section-eyebrow { justify-content: center; }
.text-center .section-sub { margin: 0 auto; }

/* ── REVEAL ANIMATION ── */
.reveal {
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1);
}
.reveal.visible { opacity: 1; transform: none; }
.reveal-delay-1 { transition-delay: 0.1s; }
.reveal-delay-2 { transition-delay: 0.2s; }
.reveal-delay-3 { transition-delay: 0.3s; }
.reveal-delay-4 { transition-delay: 0.4s; }

/* ── ATTACK FLOW — sticky horizontal ── */
#attack-flow {
  padding: 0;
}

.attack-sticky-outer {
  height: 500vh;
  position: relative;
}

.attack-sticky-inner {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--bg2);
}

.attack-header {
  text-align: center;
  padding: 48px 5% 32px;
  flex-shrink: 0;
}

.attack-track-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  overflow: hidden;
  position: relative;
}

.attack-track {
  display: flex;
  gap: 24px;
  padding: 0 10vw;
  will-change: transform;
  transition: transform 0.1s linear;
}

.attack-step {
  flex-shrink: 0;
  width: 280px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px 28px;
  transition: border-color 0.3s, background 0.3s, transform 0.3s;
  position: relative;
  overflow: hidden;
}
.attack-step::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(56,189,248,0.05), transparent);
  opacity: 0;
  transition: opacity 0.3s;
}
.attack-step.active {
  border-color: rgba(56,189,248,0.4);
  background: rgba(56,189,248,0.05);
  transform: scale(1.03);
}
.attack-step.active::before { opacity: 1; }

.step-num {
  font-family: var(--mono);
  font-size: 0.68rem;
  color: var(--cyan);
  font-weight: 700;
  letter-spacing: 0.1em;
  margin-bottom: 20px;
  opacity: 0.7;
}
.step-icon {
  width: 52px; height: 52px;
  border-radius: 12px;
  background: rgba(56,189,248,0.1);
  border: 1px solid rgba(56,189,248,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  font-size: 1.4rem;
}
.step-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--white);
}
.step-desc {
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.6;
}

.attack-progress {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 24px 5% 40px;
  flex-shrink: 0;
}
.attack-pip {
  width: 28px; height: 3px;
  border-radius: 2px;
  background: var(--border);
  transition: background 0.3s, width 0.3s;
}
.attack-pip.active { background: var(--cyan); width: 44px; }

/* ── CAPABILITIES — tilt cards ── */
#capabilities {
  padding: 100px 5%;
}

.caps-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 60px;
}

.cap-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px 28px;
  transform-style: preserve-3d;
  transform: perspective(1000px);
  transition: border-color 0.3s;
  cursor: default;
  position: relative;
  overflow: hidden;
}
.cap-card:hover { border-color: rgba(56,189,248,0.3); }
.cap-card-glare {
  position: absolute;
  inset: 0;
  border-radius: 16px;
  background: radial-gradient(circle at 50% 50%, rgba(255,255,255,0.08) 0%, transparent 60%);
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none;
}
.cap-icon {
  width: 48px; height: 48px;
  border-radius: 12px;
  background: rgba(56,189,248,0.1);
  border: 1px solid rgba(56,189,248,0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  margin-bottom: 20px;
}
.cap-title {
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--white);
}
.cap-desc {
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.65;
}

/* ── STATS SECTION ── */
#stats {
  padding: 80px 5%;
  background: var(--bg2);
}

.stats-inner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 80px;
  align-items: center;
  max-width: 1100px;
  margin: 0 auto;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 28px 24px;
  position: relative;
  overflow: hidden;
}
.stat-card::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--cyan2), var(--blue));
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.6s cubic-bezier(0.16,1,0.3,1);
}
.stat-card.counted::after { transform: scaleX(1); }
.stat-num {
  font-size: 2.6rem;
  font-weight: 700;
  color: var(--white);
  letter-spacing: -0.04em;
  line-height: 1;
  margin-bottom: 8px;
}
.stat-num span { color: var(--cyan); }
.stat-label {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
  line-height: 1.5;
}
.stat-bench {
  font-size: 0.68rem;
  color: var(--success);
  margin-top: 6px;
  font-family: var(--mono);
}

.compare-box { }
.compare-col {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 16px;
}
.compare-col.good { border-color: rgba(52,211,153,0.25); }
.compare-col.bad { border-color: rgba(248,113,113,0.15); }
.compare-head {
  padding: 14px 20px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 8px;
}
.compare-col.good .compare-head { background: rgba(52,211,153,0.07); color: var(--success); }
.compare-col.bad .compare-head { background: rgba(248,113,113,0.07); color: var(--danger); }
.compare-item {
  padding: 10px 20px;
  font-size: 0.82rem;
  color: var(--muted);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  line-height: 1.5;
}
.compare-item .icon { flex-shrink: 0; margin-top: 2px; }
.compare-item .icon.x { color: var(--danger); }
.compare-item .icon.check { color: var(--success); }

/* ── CTA ── */
#cta {
  padding: 120px 5%;
  text-align: center;
  position: relative;
  overflow: hidden;
}
#cta::before {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 600px; height: 300px;
  background: radial-gradient(ellipse, rgba(99,102,241,0.12) 0%, transparent 70%);
  pointer-events: none;
}
.cta-title {
  font-size: clamp(2rem, 4vw, 3.2rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 16px;
}
.cta-title em {
  font-style: normal;
  background: linear-gradient(135deg, var(--cyan), var(--blue2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.cta-sub {
  font-size: 1rem;
  color: var(--muted);
  margin-bottom: 40px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.65;
}
.cta-actions { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }

/* ── FOOTER ── */
footer {
  border-top: 1px solid var(--border);
  padding: 48px 5% 32px;
  position: relative;
  z-index: 2;
}
.footer-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(3, 1fr);
  gap: 48px;
  margin-bottom: 40px;
}
.footer-brand p {
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.65;
  margin-top: 12px;
  max-width: 240px;
}
.footer-col h4 {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}
.footer-col a {
  display: block;
  font-size: 0.83rem;
  color: var(--muted);
  text-decoration: none;
  margin-bottom: 8px;
  transition: color 0.2s;
}
.footer-col a:hover { color: var(--white); }
.footer-bottom {
  border-top: 1px solid var(--border);
  padding-top: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.footer-bottom p {
  font-size: 0.78rem;
  color: var(--muted);
}
.footer-bottom a { color: var(--cyan); text-decoration: none; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }

/* ── RESPONSIVE ── */
@media (max-width: 900px) {
  #hero { grid-template-columns: 1fr; padding-top: 100px; }
  .hero-left { padding-right: 0; margin-bottom: 40px; }
  .hero-right { display: none; }
  .hero-stats { grid-template-columns: 1fr; }
  .hero-stat { border-right: none; border-bottom: 1px solid var(--border); }
  .caps-grid { grid-template-columns: 1fr 1fr; }
  .stats-inner { grid-template-columns: 1fr; gap: 48px; }
  .footer-grid { grid-template-columns: 1fr 1fr; gap: 32px; }
}
@media (max-width: 600px) {
  .caps-grid { grid-template-columns: 1fr; }
  .footer-grid { grid-template-columns: 1fr; }
  .hero-stats { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="grid-bg"></div>

<!-- FLASH MESSAGES INJECTION -->
{% with messages = get_flashed_messages() %}
{% if messages %}
<div class="flash-container">
    {% for message in messages %}
    <div class="flash-message">{{ message }}</div>
    {% endfor %}
</div>
{% endif %}
{% endwith %}

<!-- NAVBAR -->
<nav id="navbar">
  <a href="/" class="nav-logo">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
    PhishSim<span>.ai</span>
  </a>
  <div class="nav-links">
    <a href="/">Home</a>
    <a href="#attack-flow">How It Works</a>
    <a href="#capabilities">Features</a>
    {% if current_user %}
        <a href="/dashboard" class="btn-nav">Dashboard</a>
    {% else %}
        <a href="/login" class="btn-nav">Login</a>
    {% endif %}
  </div>
</nav>

<!-- HERO -->
<section id="hero">
  <!-- Left -->
  <div class="hero-left">
    <div class="hero-eyebrow">Powered by Agentic AI</div>
    <h1 class="hero-h1">
      Think Like<br>an Attacker.<br>
      <em>Train Like a Pro.</em>
    </h1>
    <p class="hero-sub">
      Upload a CSV, pick a scenario, and let the AI engine craft personalized, context-aware phishing emails — then track every click before a real attacker finds your weaknesses.
    </p>
    <div class="hero-actions">
      <a href="/demo-login" class="btn-primary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        Try Live Demo
      </a>
      <a href="#attack-flow" class="btn-ghost">
        How It Works
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17l9.2-9.2M17 17V7H7"/></svg>
      </a>
    </div>
    <div class="hero-trust">
      <div class="trust-item">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20,6 9,17 4,12"/></svg>
        No credentials collected
      </div>
      <div class="trust-item">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20,6 9,17 4,12"/></svg>
        Authorized use only
      </div>
      <div class="trust-item">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20,6 9,17 4,12"/></svg>
        Setup in &lt;5 minutes
      </div>
    </div>
  </div>

  <!-- Right: Terminal -->
  <div class="hero-right">
    <div class="terminal-wrapper" id="actual-terminal-wrapper">
      <div class="terminal-bar">
        <div class="t-dots">
          <div class="t-dot red"></div>
          <div class="t-dot yellow"></div>
          <div class="t-dot green"></div>
        </div>
        <span class="t-title">agent@phishsim.ai — v2.0</span>
        <div class="t-live">LIVE</div>
      </div>
      <div class="terminal-body" id="terminal-body">
        <div class="t-logo-area">
          <img src="/static/images/terminal_logo.png" alt="PhishSim Logo" onerror="this.style.display='none'">
          <div class="t-system-name">PHISHSIM AGENTIC OS</div>
          <div class="t-system-sub">v2.0 — AUTONOMOUS SIMULATION ENGINE</div>
        </div>
        <span class="t-line t-info" id="t-mod"></span>
        <span class="t-line" id="t-llm"></span>
        <span class="t-line" id="t-db"></span>
        <span class="t-line" id="t-smtp"></span>
        <span class="t-line" id="t-osint"></span>
        <span class="t-line t-ready" id="t-ready"></span>
        <span class="t-line t-output" id="t-extra"></span>
      </div>
      <div class="terminal-input-row">
        <span>agent@phishsim:/home/agent$</span>
        <input type="text" id="t-input" placeholder="Type 'help' for commands..." autocomplete="off" spellcheck="false">
      </div>
    </div>
  </div>
</section>

<!-- STATS BAR -->
<div class="hero-stats">
  <div class="hero-stat">
    <div class="hero-stat-number" data-target="62" data-suffix="%">0%</div>
    <div class="hero-stat-label">Average Open Rate</div>
  </div>
  <div class="hero-stat">
    <div class="hero-stat-number" data-target="23" data-suffix="%">0%</div>
    <div class="hero-stat-label">Average Click Rate</div>
  </div>
  <div class="hero-stat">
    <div class="hero-stat-number" data-target="5" data-prefix="<" data-suffix=" min">0 min</div>
    <div class="hero-stat-label">Setup to First Send</div>
  </div>
</div>

<!-- ATTACK FLOW (STICKY HORIZONTAL) -->
<section id="attack-flow">
  <div class="attack-sticky-outer">
    <div class="attack-sticky-inner">
      <div class="attack-header reveal">
        <div class="section-eyebrow text-center" style="justify-content:center;">The Attack Chain</div>
        <h2 class="section-title">Anatomy of an Autonomous Attack</h2>
        <p class="section-sub text-center" style="margin:0 auto;">Scroll to watch the Agentic AI orchestrate a full-scale social engineering campaign — step by step.</p>
      </div>

      <div class="attack-track-wrapper">
        <div class="attack-track" id="attack-track">
          <div class="attack-step" data-step="0">
            <div class="step-num">STEP 01</div>
            <div class="step-icon">🔍</div>
            <div class="step-title">OSINT Gather</div>
            <div class="step-desc">The agent scrapes your company domain, LinkedIn data, and public records to build a complete target profile — just like a real attacker would.</div>
          </div>
          <div class="attack-step" data-step="1">
            <div class="step-num">STEP 02</div>
            <div class="step-icon">🧠</div>
            <div class="step-title">AI Crafting</div>
            <div class="step-desc">Using the OSINT data, the LLM generates a unique, personalized phishing email per employee — referencing their exact role, department, and company tone.</div>
          </div>
          <div class="attack-step" data-step="2">
            <div class="step-num">STEP 03</div>
            <div class="step-icon">📨</div>
            <div class="step-title">Delivery</div>
            <div class="step-desc">Emails are dispatched via SMTP directly to real employee inboxes. Each one carries a unique tracking pixel and click token.</div>
          </div>
          <div class="attack-step" data-step="3">
            <div class="step-num">STEP 04</div>
            <div class="step-icon">📡</div>
            <div class="step-title">Real-Time Tracking</div>
            <div class="step-desc">Every open, click, and report event is logged in real-time to your dashboard. You see exactly who is vulnerable — as it happens.</div>
          </div>
          <div class="attack-step" data-step="4">
            <div class="step-num">STEP 05</div>
            <div class="step-icon">📄</div>
            <div class="step-title">AI Risk Report</div>
            <div class="step-desc">The AI analyzes campaign data, identifies the most exposed departments, and generates a formatted PDF risk report ready for compliance and board reviews.</div>
          </div>
        </div>
      </div>

      <div class="attack-progress" id="attack-progress">
        <div class="attack-pip active" data-pip="0"></div>
        <div class="attack-pip" data-pip="1"></div>
        <div class="attack-pip" data-pip="2"></div>
        <div class="attack-pip" data-pip="3"></div>
        <div class="attack-pip" data-pip="4"></div>
      </div>
    </div>
  </div>
</section>

<!-- CAPABILITIES -->
<section id="capabilities">
  <div class="text-center reveal">
    <div class="section-eyebrow">Platform</div>
    <h2 class="section-title">Core Capabilities</h2>
    <p class="section-sub">Everything you need to run a professional phishing simulation — built in, not bolted on.</p>
  </div>

  <div class="caps-grid">
    <div class="cap-card reveal reveal-delay-1" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">📁</div>
      <div class="cap-title">CSV Campaign Launch</div>
      <div class="cap-desc">Upload an employee CSV and provide your company domain. PhishSim parses departments and job titles automatically — no manual setup needed.</div>
    </div>
    <div class="cap-card reveal reveal-delay-2" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">🤖</div>
      <div class="cap-title">Agentic Email Generation</div>
      <div class="cap-desc">The AI drafts a unique, context-aware phishing email for each employee — referencing their role, department, and company tone. Generated fresh every time.</div>
    </div>
    <div class="cap-card reveal reveal-delay-3" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">📊</div>
      <div class="cap-title">Real-Time Dashboards</div>
      <div class="cap-desc">Live metrics track emails sent, open rates, click rates, and report rates — updated as events happen, not in a batch at the end.</div>
    </div>
    <div class="cap-card reveal reveal-delay-1" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">🧠</div>
      <div class="cap-title">AI Risk Analysis</div>
      <div class="cap-desc">After each campaign, the AI identifies your most vulnerable departments and writes a plain-language risk summary with actionable next steps.</div>
    </div>
    <div class="cap-card reveal reveal-delay-2" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">🛡️</div>
      <div class="cap-title">Security Reports</div>
      <div class="cap-desc">Each campaign generates a detailed security posture report — highlighting what worked, who clicked, and what training to prioritize.</div>
    </div>
    <div class="cap-card reveal reveal-delay-3" data-tilt>
      <div class="cap-card-glare"></div>
      <div class="cap-icon">📄</div>
      <div class="cap-title">PDF Export</div>
      <div class="cap-desc">Download a professionally formatted PDF report in one click — audit-ready for compliance reviews, board meetings, or your security team.</div>
    </div>
  </div>
</section>

<!-- STATS + COMPARE -->
<section id="stats">
  <div class="stats-inner">
    <div>
      <div class="section-eyebrow reveal">Results</div>
      <h2 class="section-title reveal">What a Real Campaign Reveals</h2>
      <p class="section-sub reveal">Typical numbers from a PhishSim simulation on a 50-person company.</p>

      <div class="stats-grid" style="margin-top:36px">
        <div class="stat-card reveal reveal-delay-1" data-countup data-target="62" data-suffix="%">
          <div class="stat-num">0<span>%</span></div>
          <div class="stat-label">Average Open Rate</div>
          <div class="stat-bench">↑ vs 45% industry avg</div>
        </div>
        <div class="stat-card reveal reveal-delay-2" data-countup data-target="23" data-suffix="%">
          <div class="stat-num">0<span>%</span></div>
          <div class="stat-label">Average Click Rate</div>
          <div class="stat-bench">Finance dept: 38%</div>
        </div>
        <div class="stat-card reveal reveal-delay-3" data-countup data-target="8" data-suffix="%">
          <div class="stat-num">0<span>%</span></div>
          <div class="stat-label">Report Rate</div>
          <div class="stat-bench">Goal: above 40%</div>
        </div>
        <div class="stat-card reveal reveal-delay-4" data-countup data-target="5" data-prefix="<" data-suffix=" min">
          <div class="stat-num">0<span> min</span></div>
          <div class="stat-label">Setup to First Send</div>
          <div class="stat-bench">CSV → AI → dispatch</div>
        </div>
      </div>
    </div>

    <div class="compare-box reveal">
      <div class="compare-col bad">
        <div class="compare-head">
          <span class="icon x">✕</span> Without Simulation
        </div>
        <div class="compare-item"><span class="icon x">✕</span>You don't know which employees would click a real attack</div>
        <div class="compare-item"><span class="icon x">✕</span>No data on which departments are most exposed</div>
        <div class="compare-item"><span class="icon x">✕</span>Security training is generic — not based on real behaviour</div>
        <div class="compare-item"><span class="icon x">✕</span>Compliance reports have no evidence of human-layer testing</div>
      </div>
      <div class="compare-col good">
        <div class="compare-head">
          <span class="icon check">✓</span> With PhishSim AI
        </div>
        <div class="compare-item"><span class="icon check">✓</span>Know exactly who clicks before a real attacker finds out</div>
        <div class="compare-item"><span class="icon check">✓</span>Department risk scores backed by real simulation data</div>
        <div class="compare-item"><span class="icon check">✓</span>Each employee who clicks gets an instant AI teachable moment</div>
        <div class="compare-item"><span class="icon check">✓</span>AI-generated PDF report ready for audits and board meetings</div>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<section id="cta">
  <div class="section-eyebrow reveal" style="justify-content:center">Get Started</div>
  <h2 class="cta-title reveal">Ready to Find Your <em>Vulnerabilities</em>?</h2>
  <p class="cta-sub reveal">Set up your first phishing simulation in under 5 minutes. No credit card, no complicated setup — just a CSV and a company domain.</p>
  <div class="cta-actions reveal">
    <a href="/demo-login" class="btn-primary">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
      Try Live Demo
    </a>
    <a href="/signup" class="btn-ghost">Create Free Account</a>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="footer-grid">
    <div class="footer-brand">
      <a href="/" class="nav-logo" style="text-decoration:none">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--cyan)"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        PhishSim<span style="color:var(--cyan)">.ai</span>
      </a>
      <p>AI-powered phishing simulation platform. Train your team, measure risk, and build a stronger human firewall.</p>
    </div>
    <div class="footer-col">
      <h4>Product</h4>
      <a href="/demo-login">Live Demo</a>
      <a href="/signup">Get Started</a>
      <a href="#attack-flow">How It Works</a>
      <a href="/dashboard">Dashboard</a>
    </div>
    <div class="footer-col">
      <h4>Scenarios</h4>
      <a href="#">CEO Fraud</a>
      <a href="#">IT Alert</a>
      <a href="#">HR Update</a>
      <a href="#">Urgent Invoice</a>
    </div>
    <div class="footer-col">
      <h4>Legal</h4>
      <a href="#">Authorized Use Only</a>
      <a href="#">No Credentials Collected</a>
      <a href="#">Consent Required</a>
    </div>
  </div>
  <div class="footer-bottom">
    <p>© 2026 PhishSim AI — Built by <a href="https://github.com/Kavy-Sharma/phishsim-ai">Kavy Sharma</a>. For authorized security training only.</p>
    <p style="color:var(--muted);font-size:0.75rem;font-family:var(--mono)">v2.0 — AGENTIC OS</p>
  </div>
</footer>

<script>
/* ── NAVBAR SCROLL ── */
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 60);
}, { passive: true });

/* ── TERMINAL BOOT SEQUENCE ── */
const lines = [
  { id: 't-mod',   text: '[*] Loading PhishSim modules...',       cls: 't-info', delay: 400 },
  { id: 't-llm',   text: '[*] OpenRouter LLM connection... <span class="t-ok">[OK]</span>', delay: 700 },
  { id: 't-db',    text: '[*] MySQL tracking database... <span class="t-ok">[OK]</span>',   delay: 900 },
  { id: 't-smtp',  text: '[*] SMTP relay configured... <span class="t-ok">[OK]</span>',     delay: 1100 },
  { id: 't-osint', text: '[*] OSINT engine... <span class="t-passive">[PASSIVE MODE]</span>', delay: 1350 },
  { id: 't-ready', text: "PhishSim Agentic OS ready. Type 'help' for commands.", delay: 1700 },
];
lines.forEach(({ id, text, cls, delay }) => {
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el) { el.innerHTML = text; if (cls) el.classList.add(cls); }
  }, delay);
});

/* ── TERMINAL INPUT ── */
const tInput = document.getElementById('t-input');
const tBody = document.getElementById('terminal-body');
const tExtra = document.getElementById('t-extra');
const cmds = {
  help: `Available: status, campaign, report, osint, clear`,
  status: `[SYS] All modules online. 0 active campaigns.`,
  campaign: `[CMD] Campaign wizard starting...<br>[*] Awaiting CSV upload via /dashboard`,
  report: `[CMD] Last report: <span class="t-ok">No campaigns run yet.</span>`,
  osint: `[OSINT] Passive mode active. Domain scan ready.`,
  clear: '__clear__',
};
tInput && tInput.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const cmd = tInput.value.trim().toLowerCase();
  tInput.value = '';
  if (!cmd) return;
  const addLine = (html, cls = 't-output') => {
    const el = document.createElement('span');
    el.className = `t-line ${cls}`;
    el.innerHTML = html;
    tBody.insertBefore(el, document.getElementById('t-extra'));
    tBody.scrollTop = tBody.scrollHeight;
  };
  addLine(`<span class="t-prompt">agent@phishsim:/home/agent$</span> <span class="t-cmd">${cmd}</span>`);
  const res = cmds[cmd] || `bash: ${cmd}: command not found`;
  if (res === '__clear__') {
    tBody.querySelectorAll('.t-line:not(#t-mod):not(#t-llm):not(#t-db):not(#t-smtp):not(#t-osint):not(#t-ready):not(#t-extra)').forEach(el => el.remove());
    return;
  }
  setTimeout(() => addLine(res), 120);
});

/* ── INTERSECTION OBSERVER (REVEAL) ── */
const revealEls = document.querySelectorAll('.reveal');
const revealObs = new IntersectionObserver(entries => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); revealObs.unobserve(e.target); } });
}, { threshold: 0.12 });
revealEls.forEach(el => revealObs.observe(el));

/* ── COUNTUP ── */
const countEls = document.querySelectorAll('[data-countup]');
const countObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (!e.isIntersecting) return;
    const card = e.target;
    const target = +card.dataset.target;
    const suffix = card.dataset.suffix || '';
    const prefix = card.dataset.prefix || '';
    const numEl = card.querySelector('.stat-num');
    const spanContent = numEl.querySelector('span') ? numEl.querySelector('span').outerHTML : '';
    let start = 0;
    const duration = 1400;
    const startTime = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const val = Math.round(ease * target);
      numEl.innerHTML = prefix + val + spanContent;
      if (progress < 1) requestAnimationFrame(tick);
      else { numEl.innerHTML = prefix + target + spanContent; card.classList.add('counted'); }
    };
    requestAnimationFrame(tick);
    countObs.unobserve(card);
  });
}, { threshold: 0.4 });
countEls.forEach(el => countObs.observe(el));

/* ── HERO STAT COUNTUP ── */
const heroStats = document.querySelectorAll('.hero-stat-number');
const heroStatObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target;
    const target = +el.dataset.target;
    const suffix = el.dataset.suffix || '';
    const prefix = el.dataset.prefix || '';
    let start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / 1200, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + Math.round(ease * target) + suffix;
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = prefix + target + suffix;
    };
    requestAnimationFrame(tick);
    heroStatObs.unobserve(el);
  });
}, { threshold: 0.5 });
heroStats.forEach(el => heroStatObs.observe(el));

/* ── STICKY HORIZONTAL ATTACK FLOW ── */
(function() {
  const outer = document.querySelector('.attack-sticky-outer');
  const track = document.getElementById('attack-track');
  const steps = track.querySelectorAll('.attack-step');
  const pips = document.querySelectorAll('.attack-pip');
  const TOTAL = steps.length;

  const update = () => {
    const outerRect = outer.getBoundingClientRect();
    const totalScroll = outer.offsetHeight - window.innerHeight;
    const scrolled = -outerRect.top;
    const progress = Math.max(0, Math.min(1, scrolled / totalScroll));

    const cardW = 280 + 24;
    const totalTrackW = cardW * TOTAL;
    const maxShift = totalTrackW - window.innerWidth * 0.7;
    const shift = progress * maxShift;
    track.style.transform = `translateX(-${shift}px)`;

    const activeIdx = Math.min(Math.floor(progress * TOTAL), TOTAL - 1);
    steps.forEach((s, i) => s.classList.toggle('active', i === activeIdx));
    pips.forEach((p, i) => p.classList.toggle('active', i === activeIdx));
  };

  window.addEventListener('scroll', update, { passive: true });
  update();
})();

/* ── 3D TILT CARDS ── */
document.querySelectorAll('[data-tilt]').forEach(card => {
  const glare = card.querySelector('.cap-card-glare');
  card.addEventListener('mousemove', e => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const rotX = ((y - cy) / cy) * -10;
    const rotY = ((x - cx) / cx) * 10;
    card.style.transform = `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.02,1.02,1.02)`;
    if (glare) {
      const px = (x / rect.width) * 100;
      const py = (y / rect.height) * 100;
      glare.style.background = `radial-gradient(circle at ${px}% ${py}%, rgba(255,255,255,0.1) 0%, transparent 60%)`;
      glare.style.opacity = '1';
    }
  });
  card.addEventListener('mouseleave', () => {
    card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1,1,1)';
    if (glare) glare.style.opacity = '0';
  });
});
</script>
</body>
</html>"""

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(claude_html)
