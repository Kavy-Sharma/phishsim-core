import re
import os

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Terminal HTML changes - Add the tab icon
terminal_html_old = '<div class="terminal-wrapper" id="actual-terminal-wrapper" data-tilt data-tilt-max="3" data-tilt-speed="400" data-tilt-glare="true" data-tilt-max-glare="0.1">'
terminal_html_new = """<div class="terminal-wrapper" id="actual-terminal-wrapper" style="position: relative; transition: all 0.6s cubic-bezier(0.16,1,0.3,1); transform-origin: top center;" data-tilt data-tilt-max="3" data-tilt-speed="400" data-tilt-glare="true" data-tilt-max-glare="0.1">
    <div id="attached-tab" style="position: absolute; top: -35px; right: 20px; background: #000; border: 1px solid rgba(56,189,248,0.3); border-bottom: none; border-radius: 8px 8px 0 0; padding: 6px 16px; font-family: var(--mono); font-size: 0.8rem; color: var(--cyan); display: flex; align-items: center; gap: 8px; box-shadow: 0 -4px 10px rgba(56,189,248,0.1);">
        <span style="width:6px;height:6px;background:var(--cyan);border-radius:50%;box-shadow:0 0 5px var(--cyan);"></span> Agentic OS
    </div>"""
content = content.replace(terminal_html_old, terminal_html_new)

# Modify floating icon
floating_old = re.search(r'<!-- Floating Terminal Icon -->.*?</div>', content, re.DOTALL).group(0)
floating_new = """<!-- Floating Terminal Icon -->
<div id="floating-terminal-icon" onclick="restoreTerminal()" style="display: none; position: fixed; top: 100px; right: 20px; z-index: 9999; background: rgba(5,5,5,0.9); backdrop-filter: blur(10px); border: 1px solid rgba(56,189,248,0.5); border-radius: 8px; padding: 10px 20px; font-family: var(--mono); color: var(--cyan); font-weight: bold; cursor: grab; box-shadow: 0 10px 30px rgba(0,0,0,0.8), 0 0 15px rgba(56,189,248,0.2); transition: transform 0.2s ease;">
    <span style="display:inline-block; width:8px; height:8px; background:var(--cyan); border-radius:50%; margin-right:8px; box-shadow:0 0 8px var(--cyan); animation: pulse-dot 1.5s infinite;"></span>
    Terminal <i class="fas fa-expand-alt" style="margin-left: 8px; font-size: 0.8rem; opacity: 0.7;"></i>
</div>"""
content = content.replace(floating_old, floating_new)

# 2. Terminal Script changes - Inject the old VFS
vfs_script = """/* ── VIRTUAL FILE SYSTEM ── */
const vfs = {
    "home": {
        "agent": {
            "README.md": "PhishSim Agentic OS v2.0\\n================================\\nAutonomous phishing simulation engine.\\nPowered by OpenRouter LLMs + OSINT scraping.\\n\\nQuick Start:\\n  run_agent     → Launch a full simulation\\n  osint <domain>→ Scan a target domain\\n  campaigns     → List all active campaigns\\n  status        → Engine status\\n  help          → All commands",
            "campaigns": {
                "q3_finance_sim.json": '{\\n  "id": 1,\\n  "name": "Q3 Finance Phish",\\n  "scenario": "ceo_fraud",\\n  "targets": 45,\\n  "sent": 45,\\n  "opens": 27,\\n  "clicks": 8,\\n  "reports": 3,\\n  "risk_score": "HIGH",\\n  "status": "launched"\\n}',
                "hr_training_sim.json": '{\\n  "id": 2,\\n  "name": "Mandatory HR Training",\\n  "scenario": "hr_update",\\n  "targets": 30,\\n  "sent": 30,\\n  "opens": 24,\\n  "clicks": 11,\\n  "reports": 1,\\n  "risk_score": "CRITICAL",\\n  "status": "launched"\\n}'
            },
            "osint_cache": {
                "demo-corp.com.txt": "[OSINT REPORT] demo-corp.com\\n==============================\\nCompany: Demo Corporation Ltd.\\nIndustry: Financial Services\\nHeadcount: ~200 employees\\nTech Stack: Microsoft 365, Salesforce, Slack\\nExposed Subdomains: mail.demo-corp.com, hr.demo-corp.com\\nLinkedIn Employees Found: 142\\nDepartments: Finance, HR, IT, Operations, Legal\\nSenior Roles: CFO, CHRO, CTO identified\\nRisk Profile: HIGH — Microsoft 365 users are prime CEO fraud targets",
                "targets.csv": "name,email,department,title\\nAlice Sharma,alice@demo-corp.com,Finance,Accounts Manager\\nBob Patel,bob@demo-corp.com,HR,HR Business Partner\\nCarol Singh,carol@demo-corp.com,IT,Systems Admin\\nDavid Khan,david@demo-corp.com,Finance,Senior Analyst\\n... (45 total employees loaded)"
            },
            "ai_output": {
                "email_sample_1.html": "Subject: URGENT: Wire Transfer Required Before 3PM\\nFrom: CEO's Office\\n\\n<p>Alice,</p>\\n<p>I'm in back-to-back board meetings today. I need you to process a wire transfer of $47,500 for our new vendor agreement. This must go out by 3PM today.</p>\\n<p>Please click here to <a href='#'>review the payment authorization form</a>.</p>\\n<p>Do not discuss this with anyone else until confirmed. Thanks.</p>",
                "risk_report_q3.txt": "PHISHSIM AI RISK REPORT\\n=======================\\nCampaign: Q3 Finance Phish\\nRisk Level: HIGH\\n\\nKey Findings:\\n- 60% open rate (industry avg: 45%)\\n- 17.8% click rate (Finance dept most vulnerable)\\n- CEO Fraud scenario most effective\\n- 3 employees correctly reported the simulation\\n\\nAI Recommendation:\\n→ Mandatory wire-transfer verification training for Finance\\n→ Implement dual-approval policy for transactions >$10,000\\n→ Schedule follow-up simulation in 30 days"
            }
        }
    },
    "var": {
        "log": {
            "engine.log": "[2026-05-04 09:14:22] Engine boot complete\\n[2026-05-04 09:14:23] OpenRouter LLM connection: OK\\n[2026-05-04 09:14:24] MySQL connection: OK\\n[2026-05-04 09:14:25] SMTP relay: OK (Gmail)\\n[2026-05-04 09:15:01] Campaign #1 started: 45 targets\\n[2026-05-04 09:15:02] OSINT scan: demo-corp.com → 142 employees found\\n[2026-05-04 09:15:45] AI generated 45 unique phishing emails\\n[2026-05-04 09:16:12] 45/45 emails dispatched successfully",
            "events.log": "[OPEN]   alice@demo-corp.com       09:18:44\\n[OPEN]   bob@demo-corp.com         09:19:12\\n[CLICK]  alice@demo-corp.com  ⚠️   09:19:01\\n[REPORT] carol@demo-corp.com  ✅   09:21:33"
        }
    },
    "etc": {
        "phishsim.conf": '{\\n  "engine": "PhishSim Agentic OS v2.0",\\n  "llm_provider": "OpenRouter",\\n  "model": "openrouter/free",\\n  "smtp_mode": "live",\\n  "tracking": "pixel + click",\\n  "osint": "enabled",\\n  "db": "MySQL (TiDB Serverless)",\\n  "deployment": "Render.com"\\n}',
        "scenarios.json": '[\\n  "ceo_fraud    → Impersonates executive, urgent wire transfer",\\n  "hr_update    → Fake HR compliance deadline",\\n  "it_alert     → Account lockout / password reset",\\n  "invoice      → Urgent vendor invoice to finance dept"\\n]'
    }
};

let currentPath = "/home/agent";

function getDir(path) {
    if (path === '/') return vfs;
    let parts = path.split('/').filter(p => p);
    let curr = vfs;
    for (let p of parts) {
        if (curr[p] !== undefined) curr = curr[p];
        else return null;
    }
    return curr;
}

const availableCommands = ['clear', 'ls', 'cd', 'cat', 'pwd', 'whoami', 'osint', 'campaigns', 'status', 'run_agent', 'help'];

const tInput = document.getElementById('t-input');
const tBody = document.getElementById('terminal-body');

tInput.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') {
        e.preventDefault();
        const val = this.value;
        const parts = val.split(' ');
        if (parts.length === 1) {
            const matches = availableCommands.filter(c => c.startsWith(val));
            if (matches.length === 1) this.value = matches[0] + ' ';
        } else if (parts.length === 2 && (parts[0] === 'cat' || parts[0] === 'cd')) {
            const dir = getDir(currentPath);
            if (dir && typeof dir === 'object') {
                const matches = Object.keys(dir).filter(k => k.startsWith(parts[1]));
                if (matches.length === 1) this.value = parts[0] + ' ' + matches[0];
            }
        }
    }
});

tInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const val = this.value.trim();
        this.value = '';

        const line = document.createElement('div');
        line.innerHTML = `<span class="t-prompt">agent@phishsim:${currentPath}$</span> <span class="t-cmd">${val}</span>`;
        tBody.appendChild(line);

        if (val === '') { tBody.scrollTop = tBody.scrollHeight; return; }

        const args = val.split(' ').filter(a => a);
        const cmd = args[0].toLowerCase();
        let outputHTML = '';

        if (cmd === 'help') {
            outputHTML = `<div class="t-info" style="line-height:2;">
[PHISHSIM ENGINE — AVAILABLE COMMANDS]<br>
<span style="color:#06b6d4;">osint &lt;domain&gt;</span>     → Run OSINT footprint on a company domain<br>
<span style="color:#06b6d4;">campaigns</span>           → List all campaigns and live stats<br>
<span style="color:#06b6d4;">run_agent</span>           → Trigger a full simulation sequence<br>
<span style="color:#06b6d4;">status</span>              → Show engine + connection status<br>
<span style="color:#06b6d4;">ls</span>                  → List files in current directory<br>
<span style="color:#06b6d4;">cat &lt;file&gt;</span>         → Read a file<br>
<span style="color:#06b6d4;">cd &lt;dir&gt;</span>           → Change directory<br>
<span style="color:#06b6d4;">clear</span>               → Clear terminal<br>
</div>`;
        } else if (cmd === 'clear') {
            tBody.innerHTML = '';
        } else if (cmd === 'whoami') {
            outputHTML = `<div class="t-output">phishsim_agent <span style="color:#64748b;">— Autonomous Security Simulation Engine</span></div>`;
        } else if (cmd === 'pwd') {
            outputHTML = `<div class="t-output">${currentPath}</div>`;
        } else if (cmd === 'status') {
            outputHTML = `<div class="t-ok">[+] Engine: ONLINE</div>`;
            setTimeout(() => { tBody.innerHTML += `<div class="t-ok">[+] LLM: CONNECTED</div>`; tBody.scrollTop = tBody.scrollHeight; }, 200);
            setTimeout(() => { tBody.innerHTML += `<div class="t-ok">[+] MySQL: CONNECTED</div>`; tBody.scrollTop = tBody.scrollHeight; }, 400);
            setTimeout(() => { tBody.innerHTML += `<div class="t-passive">[!] OSINT: PASSIVE MODE</div>`; tBody.scrollTop = tBody.scrollHeight; }, 600);
        } else if (cmd === 'campaigns') {
            outputHTML = `<div class="t-info">Loading campaign registry...</div>`;
            setTimeout(() => { tBody.innerHTML += `<div class="t-output" style="white-space:pre;">
ID  NAME                          STATUS    TARGETS  RISK
---------------------------------------------------------
#1  Q3 Finance Phish              launched  45       HIGH
#2  Mandatory HR Training         launched  30       CRITICAL
</div>`; tBody.scrollTop = tBody.scrollHeight; }, 400);
        } else if (cmd === 'osint') {
            const target = args[1] || 'demo-corp.com';
            outputHTML = `<div class="t-passive">[!] Initiating passive OSINT footprint on: ${target}</div>`;
            setTimeout(() => { tBody.innerHTML += `<div class="t-ok">[+] 142 employee profiles discovered</div>`; tBody.scrollTop = tBody.scrollHeight; }, 1000);
            setTimeout(() => { tBody.innerHTML += `<div class="t-info">Report saved to osint_cache/${target}.txt</div>`; tBody.scrollTop = tBody.scrollHeight; }, 2000);
        } else if (cmd === 'run_agent') {
            outputHTML = `<div class="t-ok">[+] Bootstrapping PhishSim Agentic Engine...</div>`;
            setTimeout(() => { tBody.innerHTML += `<div class="t-info">Step 1/5: OSINT scan initiated...</div>`; tBody.scrollTop = tBody.scrollHeight; }, 500);
            setTimeout(() => { tBody.innerHTML += `<div class="t-info">Step 2/5: AI email generation...</div>`; tBody.scrollTop = tBody.scrollHeight; }, 1500);
            setTimeout(() => { tBody.innerHTML += `<div class="t-ok">[+] Dispatching via SMTP...</div>`; tBody.scrollTop = tBody.scrollHeight; }, 2500);
        } else if (cmd === 'ls') {
            const dir = getDir(currentPath);
            if (dir && typeof dir === 'object') {
                let items = Object.keys(dir).map(k => typeof dir[k] === 'object'
                    ? `<span style="color:#3b82f6;font-weight:bold">${k}/</span>`
                    : `<span style="color:#cbd5e1">${k}</span>`);
                outputHTML = `<div class="t-output" style="display:flex;gap:20px;flex-wrap:wrap;">${items.join('')}</div>`;
            }
        } else if (cmd === 'cd') {
            let target = args[1] || '/home/agent';
            if (target === '..') {
                if (currentPath !== '/') currentPath = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
            } else if (target === '/') {
                currentPath = '/';
            } else {
                let newPath = target.startsWith('/') ? target : (currentPath === '/' ? '/' + target : currentPath + '/' + target);
                const dir = getDir(newPath);
                if (dir && typeof dir === 'object') {
                    currentPath = newPath;
                } else {
                    outputHTML = `<div class="t-error">bash: cd: ${target}: No such file or directory</div>`;
                }
            }
            document.querySelector('.terminal-input-row span').innerText = `agent@phishsim:${currentPath}$`;
        } else if (cmd === 'cat') {
            if (!args[1]) {
                outputHTML = `<div class="t-error">cat: missing operand</div>`;
            } else {
                const dir = getDir(currentPath);
                if (dir && dir[args[1]] && typeof dir[args[1]] === 'string') {
                    outputHTML = `<div class="t-output" style="white-space:pre-wrap; color:#94a3b8; font-size:0.85rem; border-left: 2px solid #1e293b; padding-left: 12px;">${dir[args[1]]}</div>`;
                } else if (dir && dir[args[1]] && typeof dir[args[1]] === 'object') {
                    outputHTML = `<div class="t-error">cat: ${args[1]}: Is a directory</div>`;
                } else {
                    outputHTML = `<div class="t-error">cat: ${args[1]}: No such file or directory</div>`;
                }
            }
        } else {
            outputHTML = `<div class="t-error">phishsim: ${cmd}: command not found — type 'help' for commands</div>`;
        }

        if (outputHTML) {
            const outLine = document.createElement('div');
            outLine.innerHTML = outputHTML;
            tBody.appendChild(outLine);
        }
        tBody.scrollTop = tBody.scrollHeight;
    }
});"""
js_input_old = re.search(r'/\* ── TERMINAL INPUT ── \*/.*?\}\);', content, re.DOTALL).group(0)
content = content.replace(js_input_old, vfs_script)


# Terminal Animation Fix (Shrink into icon)
minimize_js_old = re.search(r'function minimizeTerminal.*?\}', content, re.DOTALL).group(0)
minimize_js_new = """function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  tWrapper.style.transform = 'scale(0.05) translate(400px, -400px) rotate(15deg)'; // Suck up into top right corner
  tWrapper.style.opacity = '0';
  setTimeout(() => {
      tWrapper.style.display = 'none';
      const icon = document.getElementById('floating-terminal-icon');
      icon.style.display = 'flex';
      icon.style.transform = 'scale(1)';
  }, 400);
}
function restoreTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  const icon = document.getElementById('floating-terminal-icon');
  icon.style.transform = 'scale(0.8)';
  setTimeout(() => {
      icon.style.display = 'none';
      tWrapper.style.display = 'block';
      setTimeout(() => {
          tWrapper.style.transform = 'scale(1) translate(0, 0) rotate(0deg)';
          tWrapper.style.opacity = '1';
      }, 50);
  }, 150);
}

// Make floating icon draggable
(function() {
    const icon = document.getElementById('floating-terminal-icon');
    let isDragging = false, startX, startY, origTop, origRight;
    icon.addEventListener('mousedown', function(e) {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = icon.getBoundingClientRect();
        origTop = rect.top;
        origRight = window.innerWidth - rect.right;
        icon.style.cursor = 'grabbing';
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        icon.style.top = Math.max(0, origTop + dy) + 'px';
        icon.style.right = Math.max(0, origRight - dx) + 'px';
    });
    document.addEventListener('mouseup', function() {
        if (isDragging) { isDragging = false; icon.style.cursor = 'grab'; }
    });
})();
"""
content = content.replace(minimize_js_old, minimize_js_new)
# Strip out the old empty restoreTerminal
content = content.replace("function restoreTerminal() {\n  const tWrapper = document.getElementById('actual-terminal-wrapper');\n  document.getElementById('floating-terminal-icon').style.display = 'none';\n  tWrapper.style.display = 'block';\n  setTimeout(() => {\n      tWrapper.style.transform = 'scale(1) translateY(0)';\n      tWrapper.style.opacity = '1';\n  }, 10);\n}", "")


# Sticky Vertical Scroll Effect for Attack Flow (Apple style)
vertical_css_old = re.search(r'/\* ── ATTACK FLOW — Vertical ── \*/.*?@media \(max-width: 768px\) \{.*?\n}', content, re.DOTALL).group(0)

vertical_css_new = """/* ── ATTACK FLOW — Sticky Scrollytelling ── */
#attack-flow {
  background: var(--bg2);
  position: relative;
  border-top: 1px solid var(--border);
}

.scrolly-container {
  display: flex;
  position: relative;
  max-width: 1400px;
  margin: 0 auto;
}

/* Left side stays sticky */
.scrolly-left {
  position: sticky;
  top: 0;
  height: 100vh;
  width: 40%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 5%;
}

.scrolly-right {
  width: 60%;
  padding: 100px 5% 100vh 5%; /* extra padding bottom to allow last card to scroll up */
}

.scrolly-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 40px;
  margin-bottom: 80vh; /* Spaced out so only one is strictly in focus */
  opacity: 0.3;
  transform: scale(0.95);
  transition: all 0.6s cubic-bezier(0.16,1,0.3,1);
  position: relative;
}
.scrolly-card.focus {
  opacity: 1;
  transform: scale(1);
  border-color: rgba(56,189,248,0.5);
  box-shadow: 0 20px 50px rgba(0,0,0,0.5), 0 0 20px rgba(56,189,248,0.1);
}
.scrolly-card:last-child { margin-bottom: 0; }

.scrolly-icon {
  width: 64px; height: 64px;
  background: rgba(56,189,248,0.1);
  border: 1px solid rgba(56,189,248,0.2);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.8rem;
  margin-bottom: 24px;
  color: var(--white);
}

.scrolly-num {
  font-family: var(--mono);
  font-size: 0.8rem;
  color: var(--cyan);
  font-weight: 700;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

@media (max-width: 900px) {
  .scrolly-container { flex-direction: column; }
  .scrolly-left { position: relative; height: auto; width: 100%; padding: 80px 5% 40px; text-align: center; }
  .scrolly-right { width: 100%; padding: 20px 5% 100px; }
  .scrolly-card { margin-bottom: 40px; opacity: 1; transform: scale(1); }
}"""
content = content.replace(vertical_css_old, vertical_css_new)

vertical_html_old = re.search(r'<!-- ATTACK FLOW \(VERTICAL\) -->\s*<section id="attack-flow">.*?</section>', content, re.DOTALL).group(0)

vertical_html_new = """<!-- ATTACK FLOW (STICKY SCROLL) -->
<section id="attack-flow">
  <div class="scrolly-container">
    <div class="scrolly-left">
      <div class="section-eyebrow">The Attack Chain</div>
      <h2 class="section-title" style="font-size: clamp(2.5rem, 4vw, 4rem);">Anatomy of an<br>Autonomous Attack</h2>
      <p class="section-sub">Scroll to watch the Agentic AI orchestrate a full-scale social engineering campaign. Each step is fully autonomous, dynamically reacting to targets.</p>
    </div>
    <div class="scrolly-right">
      
      <div class="scrolly-card scrolly-step">
        <div class="scrolly-num">STEP 01</div>
        <div class="scrolly-icon">🔍</div>
        <h3 style="font-size: 1.8rem; font-weight: 700; margin-bottom: 16px;">OSINT Gather</h3>
        <p style="font-size: 1.05rem; color: var(--muted); line-height: 1.6;">The agent scrapes your company domain, LinkedIn data, and public records to build a complete target profile — identifying departments, executives, and hierarchy.</p>
      </div>

      <div class="scrolly-card scrolly-step">
        <div class="scrolly-num">STEP 02</div>
        <div class="scrolly-icon">🧠</div>
        <h3 style="font-size: 1.8rem; font-weight: 700; margin-bottom: 16px;">AI Crafting</h3>
        <p style="font-size: 1.05rem; color: var(--muted); line-height: 1.6;">Using the OSINT data, the LLM generates a unique, personalized phishing email per employee. A junior dev gets a Jira ticket alert, while Finance gets an urgent wire request.</p>
      </div>

      <div class="scrolly-card scrolly-step">
        <div class="scrolly-num">STEP 03</div>
        <div class="scrolly-icon">📨</div>
        <h3 style="font-size: 1.8rem; font-weight: 700; margin-bottom: 16px;">Delivery</h3>
        <p style="font-size: 1.05rem; color: var(--muted); line-height: 1.6;">Emails are dispatched via SMTP directly to real employee inboxes. Each email carries a unique tracking pixel and click-tracking token to monitor engagement.</p>
      </div>

      <div class="scrolly-card scrolly-step">
        <div class="scrolly-num">STEP 04</div>
        <div class="scrolly-icon">📡</div>
        <h3 style="font-size: 1.8rem; font-weight: 700; margin-bottom: 16px;">Real-Time Tracking</h3>
        <p style="font-size: 1.05rem; color: var(--muted); line-height: 1.6;">Every open, click, and report event is logged in real-time to your dashboard. You see exactly who is vulnerable — as it happens, not days later.</p>
      </div>

      <div class="scrolly-card scrolly-step">
        <div class="scrolly-num">STEP 05</div>
        <div class="scrolly-icon">📄</div>
        <h3 style="font-size: 1.8rem; font-weight: 700; margin-bottom: 16px;">AI Risk Report</h3>
        <p style="font-size: 1.05rem; color: var(--muted); line-height: 1.6;">The AI analyzes campaign data, identifies the most exposed departments, and generates a formatted PDF risk report ready for compliance and board reviews.</p>
      </div>

    </div>
  </div>
</section>"""
content = content.replace(vertical_html_old, vertical_html_new)

scrolly_js = """
/* ── SCROLLYTELLING LOGIC ── */
const scrollyCards = document.querySelectorAll('.scrolly-step');
const scrollyObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
        e.target.classList.add('focus');
    } else {
        e.target.classList.remove('focus');
    }
  });
}, { threshold: 0.5, rootMargin: "-10% 0px -40% 0px" });

scrollyCards.forEach(card => scrollyObs.observe(card));
"""
content = content.replace("/* ── INTERSECTION OBSERVER (REVEAL) ── */", scrolly_js + "\n/* ── INTERSECTION OBSERVER (REVEAL) ── */")

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(content)
