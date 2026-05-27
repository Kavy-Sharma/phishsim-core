import sys

with open('templates/home.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'style="display: grid; grid-template-columns: repeat(4,1fr); gap: 1.5rem; margin-bottom: 3.5rem;"',
    'style="display: grid; grid-template-columns: repeat(4,1fr); gap: 1.5rem; margin-bottom: 3.5rem;" class="reveal-on-scroll countup-trigger"'
)

content = content.replace(
    'style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;"',
    'style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;" class="reveal-on-scroll"'
)

with open('templates/home.html', 'w', encoding='utf-8') as f:
    f.write(content)
