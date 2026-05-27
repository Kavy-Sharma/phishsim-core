import re

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Typography
content = content.replace('font-size: clamp(2.4rem, 4.5vw, 3.8rem);', 'font-size: clamp(3.2rem, 5.5vw, 5.2rem);')
content = content.replace('font-size: 1rem;\n  color: var(--muted);\n  line-height: 1.7;\n  max-width: 440px;', 'font-size: 1.25rem;\n  color: var(--muted);\n  line-height: 1.6;\n  max-width: 520px;')

# 2. Terminal Styling
content = content.replace('background: #0a0e1a;\n  border: 1px solid rgba(56,189,248,0.2);\n  border-radius: 14px;', 'background: #000000;\n  border: 1px solid rgba(56,189,248,0.15);\n  border-radius: 14px;')
content = content.replace('background: #111827;\n  padding: 12px 16px;', 'background: #050505;\n  padding: 12px 16px;')

# 3. Terminal Mouse Interaction (Data-Tilt)
content = content.replace('transform: perspective(1000px) rotateY(-5deg) rotateX(2deg);', '')
content = content.replace('.terminal-wrapper:hover {\n  transform: perspective(1000px) rotateY(0deg) rotateX(0deg);\n}', '')

terminal_html_old = '<div class="terminal-wrapper" id="actual-terminal-wrapper">'
terminal_html_new = '<div class="terminal-wrapper" id="actual-terminal-wrapper" data-tilt data-tilt-max="3" data-tilt-speed="400" data-tilt-glare="true" data-tilt-max-glare="0.1">'
content = content.replace(terminal_html_old, terminal_html_new)

# 4. Minimize logic fix
js_minimize_old = """let isExpanded = false;
function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  if (tWrapper.style.transform === 'scale(0.1)') {
    tWrapper.style.transform = 'perspective(1000px) rotateY(-5deg) rotateX(2deg)';
    tWrapper.style.opacity = '1';
  } else {
    tWrapper.style.transform = 'scale(0.1)';
    tWrapper.style.opacity = '0';
    setTimeout(() => {
        tWrapper.style.transform = 'perspective(1000px) rotateY(-5deg) rotateX(2deg)';
        tWrapper.style.opacity = '1';
    }, 2000); // Auto re-appear for demo
  }
}"""

js_minimize_new = """let isExpanded = false;
function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  tWrapper.style.transition = 'all 0.5s ease';
  tWrapper.style.transform = 'scale(0) translateY(200px)';
  tWrapper.style.opacity = '0';
  setTimeout(() => {
      tWrapper.style.display = 'none';
      document.getElementById('floating-terminal-icon').style.display = 'flex';
  }, 500);
}
function restoreTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  document.getElementById('floating-terminal-icon').style.display = 'none';
  tWrapper.style.display = 'block';
  setTimeout(() => {
      tWrapper.style.transform = 'scale(1) translateY(0)';
      tWrapper.style.opacity = '1';
  }, 10);
}"""
content = content.replace(js_minimize_old, js_minimize_new)

# Add floating icon to HTML
floating_icon_html = """
<!-- Floating Terminal Icon -->
<div id="floating-terminal-icon" onclick="restoreTerminal()" style="display: none; position: fixed; bottom: 30px; right: 30px; z-index: 9999; background: #000; border: 1px solid var(--cyan); border-radius: 50%; width: 60px; height: 60px; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 0 20px rgba(56,189,248,0.4); transition: transform 0.3s ease;">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
</div>
"""
content = content.replace('<div class="grid-bg"></div>', '<div class="grid-bg"></div>\n' + floating_icon_html)

# 5. Fix Attack Flow to Vertical Timeline instead of horizontal sticky scroll
horizontal_flow_css = """/* ── ATTACK FLOW — sticky horizontal ── */
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
.attack-pip.active { background: var(--cyan); width: 44px; }"""

vertical_flow_css = """/* ── ATTACK FLOW — Vertical ── */
#attack-flow {
  padding: 100px 5%;
  background: var(--bg2);
  position: relative;
}
.attack-header { text-align: center; margin-bottom: 80px; }

.vertical-timeline {
  position: relative;
  max-width: 1000px;
  margin: 0 auto;
}
.vertical-timeline::before {
  content: '';
  position: absolute;
  top: 0; left: 50%;
  transform: translateX(-50%);
  width: 2px;
  height: 100%;
  background: rgba(56,189,248,0.1);
}

.v-step {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 80px;
  position: relative;
  opacity: 0;
  transform: translateY(40px);
  transition: all 0.8s ease;
}
.v-step.visible { opacity: 1; transform: translateY(0); }
.v-step:nth-child(even) { flex-direction: row-reverse; }

.v-step-center {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 40px; height: 40px;
  background: var(--bg2);
  border: 2px solid var(--cyan);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--cyan);
  box-shadow: 0 0 20px rgba(56,189,248,0.4);
  z-index: 2;
}

.v-step-content {
  width: 45%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px;
  transition: transform 0.3s, box-shadow 0.3s;
}
.v-step-content:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  border-color: rgba(56,189,248,0.3);
}

.v-step-icon {
  font-size: 2rem;
  margin-bottom: 15px;
}
.v-step-title {
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--white);
}
.v-step-desc {
  font-size: 0.95rem;
  color: var(--muted);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .vertical-timeline::before { left: 30px; }
  .v-step { flex-direction: column !important; align-items: flex-start; padding-left: 80px; }
  .v-step-center { left: 30px; top: 0; transform: translate(-50%, 0); }
  .v-step-content { width: 100%; }
}
"""
content = content.replace(horizontal_flow_css, vertical_flow_css)

horizontal_flow_html = re.search(r'<!-- ATTACK FLOW \(STICKY HORIZONTAL\) -->.*?</section>', content, re.DOTALL).group(0)

vertical_flow_html = """<!-- ATTACK FLOW (VERTICAL) -->
<section id="attack-flow">
  <div class="attack-header reveal">
    <div class="section-eyebrow text-center" style="justify-content:center;">The Attack Chain</div>
    <h2 class="section-title">Anatomy of an Autonomous Attack</h2>
    <p class="section-sub text-center" style="margin:0 auto;">Scroll to watch the Agentic AI orchestrate a full-scale social engineering campaign.</p>
  </div>
  
  <div class="vertical-timeline">
    <div class="v-step reveal">
      <div class="v-step-center">1</div>
      <div class="v-step-content" data-tilt data-tilt-max="3" data-tilt-glare="true" data-tilt-max-glare="0.1">
        <div class="v-step-icon">🔍</div>
        <div class="v-step-title">OSINT Gather</div>
        <div class="v-step-desc">The agent scrapes your company domain, LinkedIn data, and public records to build a complete target profile — just like a real attacker would.</div>
      </div>
      <div style="width: 45%;"></div>
    </div>
    
    <div class="v-step reveal">
      <div class="v-step-center">2</div>
      <div class="v-step-content" data-tilt data-tilt-max="3" data-tilt-glare="true" data-tilt-max-glare="0.1">
        <div class="v-step-icon">🧠</div>
        <div class="v-step-title">AI Crafting</div>
        <div class="v-step-desc">Using the OSINT data, the LLM generates a unique, personalized phishing email per employee — referencing their exact role, department, and company tone.</div>
      </div>
      <div style="width: 45%;"></div>
    </div>
    
    <div class="v-step reveal">
      <div class="v-step-center">3</div>
      <div class="v-step-content" data-tilt data-tilt-max="3" data-tilt-glare="true" data-tilt-max-glare="0.1">
        <div class="v-step-icon">📨</div>
        <div class="v-step-title">Delivery</div>
        <div class="v-step-desc">Emails are dispatched via SMTP directly to real employee inboxes. Each one carries a unique tracking pixel and click token.</div>
      </div>
      <div style="width: 45%;"></div>
    </div>
    
    <div class="v-step reveal">
      <div class="v-step-center">4</div>
      <div class="v-step-content" data-tilt data-tilt-max="3" data-tilt-glare="true" data-tilt-max-glare="0.1">
        <div class="v-step-icon">📡</div>
        <div class="v-step-title">Real-Time Tracking</div>
        <div class="v-step-desc">Every open, click, and report event is logged in real-time to your dashboard. You see exactly who is vulnerable — as it happens.</div>
      </div>
      <div style="width: 45%;"></div>
    </div>
    
    <div class="v-step reveal">
      <div class="v-step-center">5</div>
      <div class="v-step-content" data-tilt data-tilt-max="3" data-tilt-glare="true" data-tilt-max-glare="0.1">
        <div class="v-step-icon">📄</div>
        <div class="v-step-title">AI Risk Report</div>
        <div class="v-step-desc">The AI analyzes campaign data, identifies the most exposed departments, and generates a formatted PDF risk report ready for compliance and board reviews.</div>
      </div>
      <div style="width: 45%;"></div>
    </div>
  </div>
</section>"""
content = content.replace(horizontal_flow_html, vertical_flow_html)

# Remove horizontal scroll JS
horizontal_js = re.search(r'/\* ── STICKY HORIZONTAL ATTACK FLOW ── \*/.*?\)\(\);', content, re.DOTALL).group(0)
content = content.replace(horizontal_js, '')

# 6. Advanced Particles Background
particle_js = """
/* ── ADVANCED PARTICLES CANVAS ── */
const canvas = document.createElement('canvas');
canvas.style.position = 'fixed';
canvas.style.top = '0';
canvas.style.left = '0';
canvas.style.width = '100vw';
canvas.style.height = '100vh';
canvas.style.zIndex = '0';
canvas.style.pointerEvents = 'none';
document.body.prepend(canvas);

const ctx = canvas.getContext('2d');
let w, h, particles;
const initCanvas = () => {
  w = canvas.width = window.innerWidth;
  h = canvas.height = window.innerHeight;
  particles = [];
  for (let i = 0; i < 80; i++) {
    particles.push({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5,
      size: Math.random() * 2 + 1
    });
  }
};
initCanvas();
window.addEventListener('resize', initCanvas);
const drawParticles = () => {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(56,189,248,0.6)';
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0 || p.x > w) p.vx *= -1;
    if (p.y < 0 || p.y > h) p.vy *= -1;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.strokeStyle = 'rgba(56,189,248,0.1)';
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 150) {
        ctx.beginPath();
        ctx.lineWidth = 1 - (dist / 150);
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.stroke();
      }
    }
  }
  requestAnimationFrame(drawParticles);
};
drawParticles();
"""

content = content.replace('/* ── CURSOR ── */', particle_js + '\n/* ── CURSOR ── */')

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(content)
