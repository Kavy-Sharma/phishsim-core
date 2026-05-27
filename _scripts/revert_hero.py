import re

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "r", encoding="utf-8") as f:
    content = f.read()

# Make hero centered again instead of side-by-side
content = content.replace(
    'style="display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; max-width: 1400px;"',
    'style="display: flex; flex-direction: column; align-items: center; text-align: center; gap: 3rem; max-width: 1000px; margin: 0 auto;"'
)

# Fix hero-left text alignment
content = content.replace('style="text-align: left;"', 'style="text-align: center; display: flex; flex-direction: column; align-items: center;"', 1)
content = content.replace('style="font-size: 4.2rem; line-height: 1.05; margin-bottom: 1.5rem; text-align: left;"', 'style="font-size: 4.2rem; line-height: 1.05; margin-bottom: 1.5rem; text-align: center;"')
content = content.replace('style="text-align: left; margin-left: 0; font-size: 1.15rem; max-width: 500px;"', 'style="text-align: center; font-size: 1.15rem; max-width: 600px; margin: 0 auto;"')
content = content.replace('style="justify-content: flex-start; margin-top: 2.5rem;"', 'style="justify-content: center; margin-top: 2.5rem;"')

# Ensure the terminal wrapper has a good style
content = content.replace('<div class="hero-right" id="hero-terminal-container">', '<div class="hero-right" id="hero-terminal-container" style="width: 100%; display: flex; justify-content: center; margin-top: 2rem;">')

with open(r"d:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html", "w", encoding="utf-8") as f:
    f.write(content)
