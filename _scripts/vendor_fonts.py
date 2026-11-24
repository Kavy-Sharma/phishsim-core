import urllib.request
import re
import os

os.makedirs('static/fonts', exist_ok=True)
url = 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=Syne:wght@700;800&display=swap'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
req = urllib.request.Request(url, headers=headers)
css_content = urllib.request.urlopen(req).read().decode('utf-8')

# Split into @font-face blocks
blocks = re.findall(r'/\* ([^*]+) \*/\s*@font-face\s*\{([^}]+)\}', css_content)

local_css_lines = []
count = 0

for subset, block in blocks:
    if 'latin' not in subset.lower():
        continue
    # Extract family, weight, style, url
    family_m = re.search(r'font-family:\s*([^;]+);', block)
    style_m = re.search(r'font-style:\s*([^;]+);', block)
    weight_m = re.search(r'font-weight:\s*([^;]+);', block)
    url_m = re.search(r'url\((https://[^)]+)\)', block)
    
    if not (family_m and weight_m and url_m):
        continue
        
    family = family_m.group(1).strip().strip("'\"")
    style = style_m.group(1).strip() if style_m else 'normal'
    weight = weight_m.group(1).strip()
    remote_url = url_m.group(1)
    
    # Safe filename
    clean_family = re.sub(r'[^a-zA-Z0-9]', '', family)
    clean_weight = re.sub(r'[^a-zA-Z0-9]', '', weight)
    clean_subset = 'latin-ext' if 'ext' in subset else 'latin'
    filename = f"{clean_family}-{clean_weight}-{style}-{clean_subset}.woff2"
    local_path = os.path.join('static/fonts', filename)
    
    if not os.path.exists(local_path):
        print(f"Downloading {filename} from {remote_url}...")
        req_font = urllib.request.Request(remote_url, headers=headers)
        with urllib.request.urlopen(req_font) as resp, open(local_path, 'wb') as f:
            f.write(resp.read())
            
    # Generate local @font-face
    entry = f"/* {subset} */\n@font-face {{\n  font-family: '{family}';\n  font-style: {style};\n  font-weight: {weight};\n  font-display: swap;\n  src: url('/static/fonts/{filename}') format('woff2');\n}}"
    local_css_lines.append(entry)
    count += 1

with open('static/fonts/fonts.css', 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(local_css_lines))

print(f"Successfully downloaded and generated static/fonts/fonts.css with {count} font faces!")
