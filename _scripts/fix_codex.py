import re

# 1. Update style.css to match home.html theme
with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\static\style.css", "r", encoding="utf-8") as f:
    css_content = f.read()

root_old = """:root {
    --bg-dark: #0f172a; /* Tailwind Slate 900 */
    --bg-darker: #020617; /* Tailwind Slate 950 */
    --bg-card: rgba(30, 41, 59, 0.7); /* Tailwind Slate 800 with opacity */
    
    --text-main: #f8fafc; /* Tailwind Slate 50 */
    --text-muted: #94a3b8; /* Tailwind Slate 400 */
    
    --accent-blue: #3b82f6; /* Tailwind Blue 500 */
    --accent-blue-hover: #2563eb; /* Tailwind Blue 600 */
    --accent-purple: #8b5cf6; /* Tailwind Violet 500 */
    --accent-cyan: #06b6d4; /* Tailwind Cyan 500 */
    
    --border-color: rgba(255, 255, 255, 0.1);"""

root_new = """:root {
    --bg-dark: #080c1a;
    --bg-darker: #05070f;
    --bg-card: rgba(255,255,255,0.04);
    
    --text-main: #f0f4ff;
    --text-muted: #8892b0;
    
    --accent-blue: #6366f1;
    --accent-blue-hover: #818cf8;
    --accent-purple: #8b5cf6;
    --accent-cyan: #38bdf8;
    
    --border-color: rgba(255,255,255,0.08);"""

css_content = css_content.replace(root_old, root_new)

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\static\style.css", "w", encoding="utf-8") as f:
    f.write(css_content)

# 2. Update home.html
with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "r", encoding="utf-8") as f:
    home_content = f.read()

# Make AI button clickable
home_content = home_content.replace('<div class="hero-eyebrow">', '<a href="/demo-login" class="hero-eyebrow" style="text-decoration:none; cursor:pointer;">')
home_content = home_content.replace('Powered by Agentic AI\n        </div>', 'Powered by Agentic AI\n        </a>')

# Increase Terminal Size
home_content = home_content.replace('min-height: 470px;', 'min-height: 570px;')
home_content = home_content.replace('max-height: 520px;', 'max-height: 650px;')

# Reduce Tilting
home_content = home_content.replace('data-tilt-max="3"', 'data-tilt-max="1"')

# Remove blocks animation (simplify minimize animation)
min_old = """function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  tWrapper.style.transform = 'scale(0.05) translate(400px, -400px) rotate(15deg)'; // Suck up into top right corner
  tWrapper.style.opacity = '0';
  setTimeout(() => {
      tWrapper.style.display = 'none';
      const icon = document.getElementById('floating-terminal-icon');
      icon.style.display = 'flex';
      icon.style.transform = 'scale(1)';
  }, 400);
}"""
min_new = """function minimizeTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  tWrapper.style.transform = 'scale(0.9)'; 
  tWrapper.style.opacity = '0';
  setTimeout(() => {
      tWrapper.style.display = 'none';
      const icon = document.getElementById('floating-terminal-icon');
      icon.style.display = 'flex';
      icon.style.transform = 'scale(1)';
  }, 300);
}"""
home_content = home_content.replace(min_old, min_new)

res_old = """function restoreTerminal() {
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
}"""
res_new = """function restoreTerminal() {
  const tWrapper = document.getElementById('actual-terminal-wrapper');
  const icon = document.getElementById('floating-terminal-icon');
  icon.style.transform = 'scale(0.8)';
  setTimeout(() => {
      icon.style.display = 'none';
      tWrapper.style.display = 'block';
      setTimeout(() => {
          tWrapper.style.transform = 'scale(1)';
          tWrapper.style.opacity = '1';
      }, 50);
  }, 150);
}"""
home_content = home_content.replace(res_old, res_new)

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(home_content)
