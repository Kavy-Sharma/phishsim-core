import re

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove network-canvas
content = re.sub(r'<!-- Network Graph Background -->\s*<canvas id="network-canvas"></canvas>', '', content)

# 2. Rewrite Hero Section to be asymmetric
hero_original = re.search(r'<!-- Hero Section -->.*?</section>', content, re.DOTALL).group(0)
hero_new = """<!-- Hero Section -->
<section class="hero-modern" id="hero" style="padding-top: 6rem; padding-bottom: 0;">
    <div class="container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; max-width: 1400px;">
        <div class="hero-left" style="text-align: left;">
            <div class="pill-badge" style="margin-left: 0; background: rgba(59, 130, 246, 0.1); border-color: rgba(59, 130, 246, 0.3); color: #60a5fa;"><i class="fas fa-shield-alt"></i> Powered by Agentic AI</div>
            <h1 class="hero-title" style="font-size: 4.2rem; line-height: 1.05; margin-bottom: 1.5rem; text-align: left;">
                Train Your Team Against<br><span style="color:var(--accent-blue);">Tomorrow's Threats.</span>
            </h1>
            <p class="hero-subtitle" style="text-align: left; margin-left: 0; font-size: 1.15rem; max-width: 500px;">Upload a CSV, pick a scenario, and let the AI engine craft personalized, context-aware emails to identify your vulnerabilities before attackers do.</p>
            <div class="hero-cta-group" style="justify-content: flex-start; margin-top: 2.5rem;">
                <a href="/demo-login" class="btn-primary" style="padding: 16px 32px; font-size: 1.1rem; box-shadow: 0 10px 25px rgba(59,130,246,0.3); border-radius: 8px;"><i class="fas fa-play-circle" style="margin-right: 8px;"></i>Try Live Demo</a>
                <a href="#attack-flow" style="color: var(--text-muted); font-weight: 600; font-size: 1rem; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; padding: 10px;" onmouseover="this.style.color='var(--text-main)'; this.style.borderBottom='2px solid var(--accent-blue)';" onmouseout="this.style.color='var(--text-muted)'; this.style.borderBottom='2px solid transparent';">How It Works</a>
            </div>
        </div>
        <div class="hero-right" id="hero-terminal-container">
            <!-- Terminal will be moved here -->
        </div>
    </div>
</section>"""
content = content.replace(hero_original, hero_new)

# 3. Move Terminal into Hero
terminal_original = re.search(r'<!-- Interactive Terminal Section -->\s*<section class="terminal-section" id="terminal-section".*?>\s*(.*?)\s*</section>', content, re.DOTALL)
if terminal_original:
    term_inner = terminal_original.group(1)
    # Remove terminal section wrapper
    content = content.replace(terminal_original.group(0), "")
    # Inject into hero-right
    term_inner_styled = f'<div style="width: 100%; max-width: 700px; transform: perspective(1000px) rotateY(-5deg) rotateX(5deg); box-shadow: -20px 20px 50px rgba(0,0,0,0.5); border-radius: 12px; transition: transform 0.5s ease;" onmouseover="this.style.transform=\'perspective(1000px) rotateY(0deg) rotateX(0deg)\'" onmouseout="this.style.transform=\'perspective(1000px) rotateY(-5deg) rotateX(5deg)\'">\n{term_inner}\n</div>'
    content = content.replace("<!-- Terminal will be moved here -->", term_inner_styled)

# 4. Sticky Horizontal Scroll for Anatomy of Attack
flow_original = re.search(r'<!-- Anatomy of an Attack -->\s*<section class="flow-section" id="attack-flow">.*?</section>', content, re.DOTALL).group(0)
flow_new = """<!-- Anatomy of an Attack (Scrollytelling) -->
<section class="flow-section" id="attack-flow" style="height: 300vh; position: relative;">
    <div class="timeline-sticky-wrapper" style="background: var(--bg-card); border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
        <div class="container" style="position: absolute; top: 10vh; left: 0; right: 0; text-align: center; z-index: 10;">
            <h2 class="section-title">The Anatomy of an Autonomous Attack</h2>
            <p class="section-subtitle">Scroll down to see how the Agentic AI orchestrates a full-scale campaign.</p>
        </div>
        <div class="timeline-horizontal-scroll" id="horizontal-scroll-container" style="margin-top: 15vh;">
            <div class="timeline-card" style="min-width: 300px; height: 350px; display: flex; flex-direction: column; justify-content: center; transform: scale(1.1);">
                <div class="card-icon"><i class="fas fa-search"></i></div>
                <h4>1. OSINT Gather</h4>
                <p>Scrapes domain & company data to find targets.</p>
            </div>
            <div class="timeline-card" style="min-width: 300px; height: 350px; display: flex; flex-direction: column; justify-content: center; transform: scale(1.1);">
                <div class="card-icon"><i class="fas fa-brain"></i></div>
                <h4>2. AI Crafting</h4>
                <p>Generates highly personalized phishing emails.</p>
            </div>
            <div class="timeline-card" style="min-width: 300px; height: 350px; display: flex; flex-direction: column; justify-content: center; transform: scale(1.1);">
                <div class="card-icon"><i class="fas fa-envelope-open-text"></i></div>
                <h4>3. Delivery</h4>
                <p>Sent via SMTP directly to real employee inboxes.</p>
            </div>
            <div class="timeline-card" style="min-width: 300px; height: 350px; display: flex; flex-direction: column; justify-content: center; transform: scale(1.1);">
                <div class="card-icon"><i class="fas fa-mouse-pointer"></i></div>
                <h4>4. Tracking</h4>
                <p>Opens, clicks & reports logged in real-time.</p>
            </div>
            <div class="timeline-card" style="min-width: 300px; height: 350px; display: flex; flex-direction: column; justify-content: center; transform: scale(1.1);">
                <div class="card-icon"><i class="fas fa-chart-bar"></i></div>
                <h4>5. AI Report</h4>
                <p>Actionable risk profile & PDF export generated.</p>
            </div>
        </div>
    </div>
</section>"""
content = content.replace(flow_original, flow_new)

# 5. Core Capabilities 3D Tilt + Scroll Reveal
content = content.replace('class="v-bar"', 'class="v-bar reveal-on-scroll" data-tilt data-tilt-max="5" data-tilt-speed="400" data-tilt-glare="true" data-tilt-max-glare="0.2"')
content = content.replace('class="v-bar active"', 'class="v-bar active reveal-on-scroll" data-tilt data-tilt-max="5" data-tilt-speed="400" data-tilt-glare="true" data-tilt-max-glare="0.2"')

# 6. Stats Animation via CountUp + Scroll Reveal
content = content.replace('class="section-title"', 'class="section-title reveal-on-scroll"')
content = content.replace('class="section-subtitle"', 'class="section-subtitle reveal-on-scroll"')

stat1 = re.search(r'>62<span', content).group(0)
content = content.replace(stat1, '><span class="countup-stat" data-val="62">0</span><span')

stat2 = re.search(r'>23<span', content).group(0)
content = content.replace(stat2, '><span class="countup-stat" data-val="23">0</span><span')

stat3 = re.search(r'>8<span', content).group(0)
content = content.replace(stat3, '><span class="countup-stat" data-val="8">0</span><span')

# Add JS logic to bottom
js_inject = """
// --- Scroll Reveal & Horizontal Scroll & CountUp ---
document.addEventListener('DOMContentLoaded', () => {
    // 1. Reveal on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                // Trigger countup if it's the stats section
                if(entry.target.classList.contains('countup-trigger') && !entry.target.counted) {
                    entry.target.counted = true;
                    document.querySelectorAll('.countup-stat').forEach(el => {
                        let val = parseInt(el.getAttribute('data-val'));
                        let cu = new countUp.CountUp(el, val, { duration: 2.5 });
                        if (!cu.error) cu.start();
                    });
                }
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.reveal-on-scroll').forEach(el => observer.observe(el));
    
    // Add trigger for countup
    const statsContainer = document.querySelector('.countup-stat').closest('div').parentElement;
    statsContainer.classList.add('reveal-on-scroll', 'countup-trigger');
    observer.observe(statsContainer);

    // 2. Horizontal Scroll for Attack Flow
    const flowSection = document.getElementById('attack-flow');
    const scrollContainer = document.getElementById('horizontal-scroll-container');
    
    window.addEventListener('scroll', () => {
        if(!flowSection || !scrollContainer) return;
        const rect = flowSection.getBoundingClientRect();
        const scrollPercent = Math.max(0, Math.min(1, -rect.top / (rect.height - window.innerHeight)));
        
        // Translate horizontally based on scroll percentage
        const maxScroll = scrollContainer.scrollWidth - window.innerWidth + 400; 
        scrollContainer.style.transform = `translateX(-${scrollPercent * maxScroll}px)`;
    });
});
"""

# Inject JS before endblock
content = content.replace('{% endblock %}', f'<style>\n.reveal-on-scroll {{ opacity: 0; transform: translateY(30px); transition: all 0.8s cubic-bezier(0.4, 0, 0.2, 1); }}\n.reveal-on-scroll.revealed {{ opacity: 1; transform: translateY(0); }}\n</style>\n{js_inject}\n{{% endblock %}}')

# Remove old canvas script
canvas_script = re.search(r'// --- Advanced Interactive Network Graph ---.*?animate\(\);\s*', content, re.DOTALL)
if canvas_script:
    content = content.replace(canvas_script.group(0), '')

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(content)
