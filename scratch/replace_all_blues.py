import re

def pct_str(val):
    p = float(val) * 100
    if p.is_integer():
        return f"{int(p)}%"
    else:
        return f"{p:.1f}%"

def replace_blues(content):
    # List of hex values to replace (case-insensitive)
    hex_replacements = [
        (r'#06b6d4', 'var(--primary)'),
        (r'#06B6D4', 'var(--primary)'),
        (r'#2563eb', 'var(--primary)'),
        (r'#2563EB', 'var(--primary)'),
        (r'#3b82f6', 'var(--primary)'),
        (r'#3B82F6', 'var(--primary)'),
        (r'#0ea5e9', 'var(--primary)'),
        (r'#0EA5E9', 'var(--primary)'),
        (r'#60a5fa', 'var(--primary)'),
        (r'#60A5FA', 'var(--primary)'),
        (r'#22d3ee', 'var(--primary)'),
        (r'#22D3EE', 'var(--primary)'),
        (r'#00f0ff', 'var(--primary)'),
        (r'#00F0FF', 'var(--primary)'),
        (r'#00d2ff', 'var(--primary)'),
        (r'#00D2FF', 'var(--primary)'),
        (r'#0284c7', 'var(--primary)'),
        (r'#0284C7', 'var(--primary)'),
        (r'#0e74c8', 'var(--primary)'),
        (r'#0E74C8', 'var(--primary)'),
        (r'#1d4ed8', 'var(--primary)'),
        (r'#1D4ED8', 'var(--primary)'),
        (r'#1e3a8a', 'var(--primary)'),
        (r'#1E3A8A', 'var(--primary)'),
        (r'#7dd3fc', 'var(--primary)'),
        (r'#7DD3FC', 'var(--primary)'),
        (r'#e0f2fe', 'var(--primary)'),
        (r'#E0F2FE', 'var(--primary)'),
    ]

    for old_hex, new_val in hex_replacements:
        content = re.sub(old_hex, new_val, content)

    # List of RGB components to replace
    # Format: (R, G, B)
    rgb_patterns = [
        (6, 182, 212),    # Cyan-500
        (37, 99, 235),    # Blue-600
        (59, 130, 246),   # Blue-500
        (14, 165, 233),   # Sky-500
        (0, 240, 255),    # Neon Cyan
        (14, 116, 200),   # Brand Blue
        (125, 211, 252),  # Sky-300
    ]

    for r, g, b in rgb_patterns:
        # Match rgba(r, g, b, alpha)
        # Handle spaces and no-spaces
        pattern = rf'rgba\({r},\s*{g},\s*{b},\s*([\d\.]+)\)'
        content = re.sub(
            pattern,
            lambda m: f'color-mix(in srgb, var(--primary) {pct_str(m.group(1))}, transparent)',
            content
        )
        pattern_nospace = rf'rgba\({r},{g},{b},([\d\.]+)\)'
        content = re.sub(
            pattern_nospace,
            lambda m: f'color-mix(in srgb, var(--primary) {pct_str(m.group(1))}, transparent)',
            content
        )

    return content

if __name__ == '__main__':
    file_path = r'd:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html'
    print("Reading templates/home.html...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = replace_blues(content)

    print("Writing templates/home.html...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("Successfully replaced all remaining blue colors!")
