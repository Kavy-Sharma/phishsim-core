import os
import re

# 1. Update style.css to include the new fonts
with open(r'd:\Projects\Phishsim AI\Phishsim.ai-Core\static\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

if '--font-mono' not in css:
    css = css.replace("--font-sans: 'Space Grotesk', sans-serif;", "--font-sans: 'Space Grotesk', sans-serif;\n    --font-mono: 'JetBrains Mono', monospace;")

with open(r'd:\Projects\Phishsim AI\Phishsim.ai-Core\static\style.css', 'w', encoding='utf-8') as f:
    f.write(css)

# 2. Iterate through all templates and replace Outfit/Space Mono with var(--font-sans)/var(--font-mono)
templates_dir = r'd:\Projects\Phishsim AI\Phishsim.ai-Core\templates'
for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
            
        # Replace fonts
        html = re.sub(r"'Outfit',\s*sans-serif", "var(--font-sans)", html)
        html = re.sub(r'"Outfit",\s*sans-serif', "var(--font-sans)", html)
        html = re.sub(r"'Space Mono',\s*monospace", "var(--font-mono)", html)
        html = re.sub(r'"Space Mono",\s*monospace', "var(--font-mono)", html)
        
        # Remove hardcoded CSS that might break the dark theme
        if filename == 'dashboard.html':
            html = html.replace("background: var(--bg-card, rgba(10, 16, 38, 0.9));", "background: var(--surface);")
            html = html.replace("background: var(--bg-card, rgba(15,23,42,0.7));", "background: var(--surface);")
            html = html.replace("background: var(--bg-card, rgba(15,23,42,0.5));", "background: var(--surface);")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

# 3. Update home.html with specific terminal requests
home_path = os.path.join(templates_dir, 'home.html')
with open(home_path, 'r', encoding='utf-8') as f:
    home_html = f.read()

# Fix default terminal height
if 'min-height: 570px;' in home_html:
    home_html = home_html.replace('min-height: 570px;', 'min-height: 700px;')
    home_html = home_html.replace('max-height: 650px;', 'max-height: 800px;')

# Reduce tilt
if 'data-tilt-max="3"' in home_html:
    home_html = home_html.replace('data-tilt-max="3"', 'data-tilt-max="1"')

# Fix minimize animation (no blocks, keep dots in icon)
minimize_js_old = re.search(r'function minimizeTerminal\(\) \{.*?\n\}', home_html, re.DOTALL)
if minimize_js_old:
    minimize_js_new = """function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  tWrapper.style.transform = 'scale(0.8)';
  tWrapper.style.opacity = '0';
  setTimeout(() => {
      tWrapper.style.display = 'none';
      const icon = document.getElementById('floating-terminal-icon');
      icon.style.display = 'flex';
      icon.style.transform = 'scale(1)';
  }, 200);
}"""
    home_html = home_html.replace(minimize_js_old.group(0), minimize_js_new)

# Make sure floating icon has the dots
floating_old = re.search(r'<!-- Floating Terminal Icon -->.*?</div>', home_html, re.DOTALL)
if floating_old:
    if 't-dot red' not in floating_old.group(0):
        floating_new = """<!-- Floating Terminal Icon -->
<div id="floating-terminal-icon" onclick="restoreTerminal()" style="display: none; position: fixed; top: 100px; right: 20px; z-index: 9999; background: rgba(5,5,5,0.9); backdrop-filter: blur(10px); border: 1px solid rgba(56,189,248,0.5); border-radius: 8px; padding: 10px 20px; cursor: grab; box-shadow: 0 10px 30px rgba(0,0,0,0.8), 0 0 15px rgba(56,189,248,0.2); transition: transform 0.2s ease; flex-direction: row; align-items: center; gap: 15px;">
    <div style="display: flex; gap: 8px;">
        <div class="t-dot red"></div>
        <div class="t-dot yellow"></div>
        <div class="t-dot green"></div>
    </div>
    <span style="font-family: var(--mono); color: var(--cyan); font-weight: bold;">Terminal</span>
    <span style="display:inline-block; width:8px; height:8px; background:var(--cyan); border-radius:50%; box-shadow:0 0 8px var(--cyan); animation: pulse-dot 1.5s infinite;"></span>
</div>"""
        home_html = home_html.replace(floating_old.group(0), floating_new)

# Fix AI button clickable
# Maybe the pill-badge is what they mean?
pill = '<div class="pill-badge"'
pill_new = '<div class="pill-badge" style="cursor:pointer;" onclick="window.location.href=\'/signup\'"'
if pill in home_html and pill_new not in home_html:
    home_html = home_html.replace(pill, pill_new)

with open(home_path, 'w', encoding='utf-8') as f:
    f.write(home_html)

print("Done updating files!")
