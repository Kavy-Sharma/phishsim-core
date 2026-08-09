import re

def update_home_html(content):
    # 1. Remove custom/hardcoded root theme variable definitions in home.html
    # We target the blocks `:root, :root[data-theme="dark"]` and `:root[data-theme="light"]`
    
    # Let's locate the :root block for dark mode and remove the primary, danger, warning, success, info variables.
    dark_root_pattern = r'(:root,\s*:root\[data-theme="dark"\]\s*\{)(.*?)(^\s*\})'
    def dark_root_replace(match):
        header = match.group(1)
        body = match.group(2)
        footer = match.group(3)
        
        # We want to remove variables: --primary, --primary-dim, --primary-glow, --danger, --danger-dim, --danger-glow, --warning, --warning-dim, --success, --success-dim, --info, --info-dim
        vars_to_remove = [
            '--primary', '--primary-dim', '--primary-glow',
            '--danger', '--danger-dim', '--danger-glow',
            '--warning', '--warning-dim',
            '--success', '--success-dim',
            '--info', '--info-dim'
        ]
        
        lines = body.split('\n')
        new_lines = []
        for line in lines:
            stripped = line.strip()
            # If the line contains a variable to remove, skip it
            if any(stripped.startswith(v + ':') for v in vars_to_remove):
                continue
            # Also clean up headers/comments related to these variables
            if stripped.startswith('/* === PRIMARY') or stripped.startswith('/* === DANGER') or stripped.startswith('/* === WARNING') or stripped.startswith('/* === SUCCESS') or stripped.startswith('/* === INFO'):
                continue
            new_lines.append(line)
        
        return header + '\n'.join(new_lines) + footer

    content = re.sub(dark_root_pattern, dark_root_replace, content, flags=re.DOTALL | re.MULTILINE)

    # Let's locate the :root block for light mode and remove the variables too.
    light_root_pattern = r'(:root\[data-theme="light"\]\s*\{)(.*?)(^\s*\})'
    def light_root_replace(match):
        header = match.group(1)
        body = match.group(2)
        footer = match.group(3)
        
        vars_to_remove = [
            '--primary', '--primary-dim', '--primary-glow',
            '--danger', '--danger-dim', '--danger-glow',
            '--warning', '--warning-dim',
            '--success', '--success-dim',
            '--info', '--info-dim'
        ]
        
        lines = body.split('\n')
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(v + ':') for v in vars_to_remove):
                continue
            if stripped.startswith('/* === PRIMARY') or stripped.startswith('/* === DANGER') or stripped.startswith('/* === WARNING') or stripped.startswith('/* === SUCCESS') or stripped.startswith('/* === INFO'):
                continue
            new_lines.append(line)
        
        return header + '\n'.join(new_lines) + footer

    content = re.sub(light_root_pattern, light_root_replace, content, flags=re.DOTALL | re.MULTILINE)

    # 2. Replaces of var(--primary, #38BDF8) fallback usages
    # Replace all var(--primary, #38BDF8) with var(--primary)
    content = re.sub(r'var\(--primary,\s*#38[Bb][Dd][Ff]8\)', 'var(--primary)', content)
    content = re.sub(r'var\(--primary-dim,\s*rgba\(56,\s*189,\s*248,\s*[\d\.]+\)\)', 'var(--primary-dim)', content)
    content = re.sub(r'var\(--primary-dim,\s*rgba\(56,189,248,[\d\.]+\)\)', 'var(--primary-dim)', content)
    content = re.sub(r'var\(--warning,\s*#FB923C\)', 'var(--warning)', content)
    content = re.sub(r'var\(--warning,\s*#fb923c\)', 'var(--warning)', content)
    content = re.sub(r'var\(--warning,\s*#FB923C\)', 'var(--warning)', content)
    content = re.sub(r'var\(--danger,\s*#F87171\)', 'var(--danger)', content)

    # 3. Specific replacements for box-shadows / decorative glows (reducing blur and opacity)
    shadow_replacements = [
        ('box-shadow: 0 0 10px #06b6d4, 0 0 20px #06b6d4;', 'box-shadow: 0 0 5px rgba(6, 182, 212, 0.6), 0 0 10px rgba(6, 182, 212, 0.6);'),
        ('box-shadow: 0 12px 40px rgba(6, 182, 212, 0.2);', 'box-shadow: 0 12px 20px rgba(6, 182, 212, 0.13);'),
        ('box-shadow: 0 15px 35px var(--card-glow-color-shadow, rgba(6, 182, 212, 0.15));', 'box-shadow: 0 15px 20px var(--card-glow-color-shadow, rgba(6, 182, 212, 0.1));'),
        ('box-shadow: 0 15px 35px rgba(6, 182, 212, 0.15);', 'box-shadow: 0 15px 20px rgba(6, 182, 212, 0.1);'),
        ('box-shadow: 0 0 15px rgba(6, 182, 212, 0.2);', 'box-shadow: 0 0 8px rgba(6, 182, 212, 0.12);'),
        ('box-shadow: 0 4px 14px var(--primary-glow) !important;', 'box-shadow: 0 4px 8px color-mix(in srgb, var(--primary) 15%, transparent) !important;'),
        ('box-shadow: 0 6px 20px var(--primary-glow) !important;', 'box-shadow: 0 6px 10px color-mix(in srgb, var(--primary) 15%, transparent) !important;'),
        ('box-shadow: 0 8px 30px rgba(14, 165, 233, 0.4);', 'box-shadow: 0 8px 15px rgba(14, 165, 233, 0.24);'),
        ('box-shadow: 0 0 20px rgba(6, 182, 212, 0.3);', 'box-shadow: 0 0 10px rgba(6, 182, 212, 0.18);'),
        ('box-shadow: 0 0 25px rgba(6, 182, 212, 0.5);', 'box-shadow: 0 0 15px rgba(6, 182, 212, 0.3);'),
        ('box-shadow: 0 18px 42px rgba(0, 0, 0, 0.34), 0 0 26px rgba(56, 189, 248, 0.18);', 'box-shadow: 0 18px 42px rgba(0, 0, 0, 0.34), 0 0 15px color-mix(in srgb, var(--primary) 11%, transparent);'),
        ('box-shadow: 0 22px 50px rgba(0, 0, 0, 0.42), 0 0 36px rgba(56, 189, 248, 0.3);', 'box-shadow: 0 22px 50px rgba(0, 0, 0, 0.42), 0 0 20px color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('box-shadow: 0 18px 42px rgba(37, 99, 235, 0.16);', 'box-shadow: 0 18px 22px color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('0 0 140px rgba(0, 240, 255, 0.35)', '0 0 80px rgba(0, 240, 255, 0.22)'),
        ('0 0 180px rgba(255, 0, 127, 0.45)', '0 0 100px rgba(255, 0, 127, 0.28)'),
        ('box-shadow: 0 0 10px rgba(56, 189, 248, 0.38);', 'box-shadow: 0 0 6px color-mix(in srgb, var(--primary) 24%, transparent);'),
        ('box-shadow: 0 18px 45px rgba(0, 0, 0, 0.45), 0 0 28px rgba(56, 189, 248, 0.16);', 'box-shadow: 0 18px 45px rgba(0, 0, 0, 0.45), 0 0 15px color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('box-shadow: 0 0 18px rgba(56, 189, 248, 0.82), 0 0 42px rgba(99, 102, 241, 0.38);', 'box-shadow: 0 0 10px color-mix(in srgb, var(--primary) 50%, transparent), 0 0 22px rgba(99, 102, 241, 0.24);'),
        ('box-shadow: 0 0 14px rgba(56, 189, 248, 0.9);', 'box-shadow: 0 0 8px color-mix(in srgb, var(--primary) 55%, transparent);'),
        ('box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42), 0 0 36px rgba(56, 189, 248, 0.12);', 'box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42), 0 0 20px color-mix(in srgb, var(--primary) 8%, transparent);'),
        ('box-shadow: inset 0 0 18px rgba(56, 189, 248, 0.08);', 'box-shadow: inset 0 0 10px color-mix(in srgb, var(--primary) 5%, transparent);'),
        ('box-shadow: inset 0 0 48px rgba(56, 189, 248, 0.06), 0 24px 80px rgba(0, 0, 0, 0.26);', 'box-shadow: inset 0 0 24px color-mix(in srgb, var(--primary) 4%, transparent), 0 24px 80px rgba(0, 0, 0, 0.26);'),
        ('box-shadow: 0 0 38px rgba(56, 189, 248, 0.24);', 'box-shadow: 0 0 20px color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('box-shadow: 0 0 54px rgba(56, 189, 248, 0.38);', 'box-shadow: 0 0 28px color-mix(in srgb, var(--primary) 24%, transparent);'),
        ('box-shadow: 0 0 28px rgba(56, 189, 248, 0.22);', 'box-shadow: 0 0 15px color-mix(in srgb, var(--primary) 14%, transparent);'),
        ('box-shadow: 0 0 18px rgba(56, 189, 248, 0.42);', 'box-shadow: 0 0 10px color-mix(in srgb, var(--primary) 26%, transparent);'),
        ('box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 30px rgba(6, 182, 212, 0.35) !important;', 'box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 16px rgba(6, 182, 212, 0.22) !important;'),
        ('box-shadow: 0 0 10px rgba(56, 189, 248, 0.15);', 'box-shadow: 0 0 6px color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('box-shadow: 0 0 10px rgba(251,191,36,0.25);', 'box-shadow: 0 0 6px color-mix(in srgb, var(--warning) 16%, transparent);'),
        ('box-shadow: 0 0 0 6px rgba(251, 191, 36, 0.18), 0 16px 48px rgba(251, 191, 36, 0.22) !important;', 'box-shadow: 0 0 0 6px color-mix(in srgb, var(--warning) 12%, transparent), 0 16px 28px color-mix(in srgb, var(--warning) 14%, transparent) !important;'),
        ('box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);', 'box-shadow: 0 0 6px color-mix(in srgb, var(--primary) 25%, transparent);'),
        ('box-shadow: 0 0 30px rgba(6, 182, 212, 0.1);', 'box-shadow: 0 0 16px rgba(6, 182, 212, 0.06);'),
        ('box-shadow: 0 0 30px rgba(239,68,68,0.05);', 'box-shadow: 0 0 16px color-mix(in srgb, var(--danger) 3%, transparent);'),
        ('box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);', 'box-shadow: 0 0 6px color-mix(in srgb, var(--danger) 12%, transparent);'),
        ('box-shadow: 0 0 25px rgba(239, 68, 68, 0.6);', 'box-shadow: 0 0 14px color-mix(in srgb, var(--danger) 38%, transparent);'),
        ('box-shadow: 0 0 25px rgba(56, 189, 248, 0.45) !important;', 'box-shadow: 0 0 14px color-mix(in srgb, var(--primary) 28%, transparent) !important;'),
        ('0 0 10px #2563eb, 0 0 20px rgba(37, 99, 235, 0.4);', '0 0 5px color-mix(in srgb, var(--primary) 60%, transparent), 0 0 10px color-mix(in srgb, var(--primary) 25%, transparent);'),
        ('box-shadow: 0 8px 32px rgba(37, 99, 235, 0.12);', 'box-shadow: 0 8px 16px color-mix(in srgb, var(--primary) 8%, transparent);'),
        ('box-shadow: 0 18px 48px rgba(37, 99, 235, 0.08);', 'box-shadow: 0 18px 24px color-mix(in srgb, var(--primary) 5%, transparent);'),
        ('box-shadow: 0 20px 40px rgba(37, 99, 235, 0.06) !important;', 'box-shadow: 0 20px 20px color-mix(in srgb, var(--primary) 4%, transparent) !important;'),
        ('box-shadow: 0 10px 40px rgba(37, 99, 235, 0.05) !important;', 'box-shadow: 0 10px 20px color-mix(in srgb, var(--primary) 3%, transparent) !important;'),
        ('box-shadow: 0 8px 32px rgba(37, 99, 235, 0.03) !important;', 'box-shadow: 0 8px 16px color-mix(in srgb, var(--primary) 2%, transparent) !important;'),
        ('box-shadow: 0 12px 28px rgba(37, 99, 235, 0.18);', 'box-shadow: 0 12px 15px color-mix(in srgb, var(--primary) 11%, transparent);'),
        ('box-shadow: 0 12px 28px rgba(37, 99, 235, 0.18) !important;', 'box-shadow: 0 12px 15px color-mix(in srgb, var(--primary) 11%, transparent) !important;'),
        ('box-shadow: 0 24px 70px rgba(37, 99, 235, 0.1);', 'box-shadow: 0 24px 35px color-mix(in srgb, var(--primary) 7%, transparent);'),
        ('box-shadow: 0 12px 40px rgba(37, 99, 235, 0.08);', 'box-shadow: 0 12px 20px color-mix(in srgb, var(--primary) 5%, transparent);'),
        ('box-shadow: 0 12px 40px rgba(37, 99, 235, 0.15);', 'box-shadow: 0 12px 20px color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('box-shadow: 0 26px 72px rgba(0, 0, 0, 0.34), 0 0 34px var(--cap-accent);', 'box-shadow: 0 26px 72px rgba(0, 0, 0, 0.34), 0 0 18px var(--cap-accent);'),
        ('box-shadow: 0 0 30px rgba(6, 182, 212, 0.05), inset 0 0 10px rgba(6, 182, 212, 0.05);', 'box-shadow: 0 0 16px rgba(6, 182, 212, 0.03), inset 0 0 6px rgba(6, 182, 212, 0.03);'),
        ('box-shadow: 0 0 45px rgba(6, 182, 212, 0.12), inset 0 0 15px rgba(6, 182, 212, 0.10);', 'box-shadow: 0 0 24px rgba(6, 182, 212, 0.07), inset 0 0 9px rgba(6, 182, 212, 0.06);'),
        ('box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 30px rgba(6, 182, 212, 0.35) !important;', 'box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 16px rgba(6, 182, 212, 0.22) !important;'),
        ('box-shadow: 0 5px 15px rgba(6, 182, 212, 0.25);', 'box-shadow: 0 5px 8px rgba(6, 182, 212, 0.15);'),
        ('box-shadow: 0 0 20px rgba(6, 182, 212, 0.08);', 'box-shadow: 0 0 10px rgba(6, 182, 212, 0.05);'),
        ('box-shadow: 0 0 10px rgba(6, 182, 212, 0.15);', 'box-shadow: 0 0 6px rgba(6, 182, 212, 0.09);'),
        ('box-shadow: 0 0 10px rgba(0, 240, 255, 0.2);', 'box-shadow: 0 0 6px rgba(0, 240, 255, 0.12);'),
        ('box-shadow: 0 0 8px #00f0ff;', 'box-shadow: 0 0 5px rgba(0, 240, 255, 0.6);'),
        ('box-shadow: 0 0 15px rgba(0, 240, 255, 0.6), 0 0 30px rgba(255, 0, 127, 0.4);', 'box-shadow: 0 0 9px rgba(0, 240, 255, 0.38), 0 0 16px rgba(255, 0, 127, 0.25);'),
        ('box-shadow: 0 0 15px rgba(255, 0, 127, 0.6), 0 0 30px rgba(234, 179, 8, 0.4);', 'box-shadow: 0 0 9px rgba(255, 0, 127, 0.38), 0 0 16px rgba(234, 179, 8, 0.25);'),
        ('box-shadow: 0 0 15px rgba(234, 179, 8, 0.6), 0 0 30px rgba(0, 240, 255, 0.4);', 'box-shadow: 0 0 9px rgba(234, 179, 8, 0.38), 0 0 16px rgba(0, 240, 255, 0.25);'),
        ('box-shadow: 0 0 15px rgba(0, 240, 255, 0.6), 0 0 30px rgba(255, 0, 127, 0.4);', 'box-shadow: 0 0 9px rgba(0, 240, 255, 0.38), 0 0 16px rgba(255, 0, 127, 0.25);'),
        ('box-shadow: 0 0 18px rgba(248,113,113,0.22) !important;', 'box-shadow: 0 0 10px color-mix(in srgb, var(--danger) 14%, transparent) !important;'),
        ('card.style.boxShadow = `${shadowOffsetX}px ${shadowOffsetY}px ${shadowBlur}px rgba(0,0,0,0.4), 0 0 24px rgba(56,189,248,0.06)`;', 'card.style.boxShadow = `${shadowOffsetX}px ${shadowOffsetY}px ${shadowBlur}px rgba(0,0,0,0.4), 0 0 12px color-mix(in srgb, var(--primary) 4%, transparent)`;'),
        ('style="position: absolute; content: \'\'; height: 18px; width: 18px; left: 4px; bottom: 3px; background-color: #38bdf8; border-radius: 50%; transition: 0.3s; box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);"', 'style="position: absolute; content: \'\'; height: 18px; width: 18px; left: 4px; bottom: 3px; background-color: var(--primary); border-radius: 50%; transition: 0.3s; box-shadow: 0 0 6px color-mix(in srgb, var(--primary) 25%, transparent);"'),
        ('box-shadow:0 4px 6px rgba(245,158,11,0.2);', 'box-shadow:0 4px 4px color-mix(in srgb, var(--warning) 12%, transparent);'),
    ]
    for old_s, new_s in shadow_replacements:
        content = content.replace(old_s, new_s)

    # 4. Specific replacements for solid borders with 30-40% opacity (reducing opacity to 15-22%)
    border_replacements = [
        ('border: 1.5px solid color-mix(in srgb, var(--primary, #38BDF8) 40%, transparent);', 'border: 1.5px solid color-mix(in srgb, var(--primary) 20%, transparent);'),
        ('border-color: color-mix(in srgb, var(--primary, #38BDF8) 80%, transparent);', 'border-color: color-mix(in srgb, var(--primary) 22%, transparent);'),
        ('border: 1.5px solid color-mix(in srgb, var(--primary, #38BDF8) 28%, transparent);', 'border: 1.5px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary, #38BDF8) 30%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary,#38BDF8) 22%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary,#38BDF8) 25%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary,#38BDF8) 16%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('border-color: color-mix(in srgb, var(--primary,#38BDF8) 30%, transparent);', 'border-color: color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border-color: color-mix(in srgb, var(--primary,#38BDF8) 22%, transparent);', 'border-color: color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('border-color: color-mix(in srgb, var(--primary,#38BDF8) 32%, transparent);', 'border-color: color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1.5px solid color-mix(in srgb, var(--primary,#38BDF8) 45%, transparent);', 'border: 1.5px solid color-mix(in srgb, var(--primary) 20%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary,#38BDF8) 28%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1px solid color-mix(in srgb, var(--primary,#38BDF8) 20%, transparent);', 'border: 1px solid color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('border-color:color-mix(in srgb,var(--primary,#38BDF8) 32%,transparent);', 'border-color: color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border-color:color-mix(in srgb,var(--warning,#FB923C) 32%,transparent);', 'border-color: color-mix(in srgb, var(--warning) 18%, transparent);'),
        ('border-color:color-mix(in srgb,var(--warning,#FB923C) 32%,transparent)', 'border-color:color-mix(in srgb,var(--warning) 18%,transparent)'),
        ('border-color:color-mix(in srgb,var(--primary,#38BDF8) 32%,transparent)', 'border-color:color-mix(in srgb,var(--primary) 18%,transparent)'),
        ('border-color:rgba(56,189,248,0.4)', 'border-color:color-mix(in srgb, var(--primary) 20%, transparent)'),
        ('borderBottomColor=\'rgba(56,189,248,0.4)\'', 'borderBottomColor=\'color-mix(in srgb, var(--primary) 20%, transparent)\''),
        ('border-bottom: 1px dashed rgba(56,189,248,0.4);', 'border-bottom: 1px dashed color-mix(in srgb, var(--primary) 20%, transparent);'),
        ('border-bottom: 1px dashed rgba(245,158,11,0.4);', 'border-bottom: 1px dashed color-mix(in srgb, var(--warning) 20%, transparent);'),
        ('borderBottomColor=\'rgba(245,158,11,0.4)\'', 'borderBottomColor=\'color-mix(in srgb, var(--warning) 20%, transparent)\''),
        ('border: 2px solid #ef4444;', 'border: 1.5px solid var(--danger);'),
        ('border-left:4px solid #ef4444;', 'border-left:3px solid var(--danger);'),
        ('border:1px solid rgba(239, 68, 68, 0.3);', 'border:1px solid color-mix(in srgb, var(--danger) 18%, transparent);'),
        ('border: 1px solid rgba(251,191,36,0.45);', 'border: 1px solid color-mix(in srgb, var(--warning) 18%, transparent);'),
        ('border: 1px solid rgba(251, 191, 36, 0.45);', 'border: 1px solid color-mix(in srgb, var(--warning) 18%, transparent);'),
        ('border: 1px solid rgba(56, 189, 248, 0.15);', 'border: 1px solid color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('border: 1px solid rgba(56, 189, 248, 0.2);', 'border: 1px solid color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('border: 1px solid rgba(56, 189, 248, 0.22);', 'border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border: 1px solid rgba(56, 189, 248, 0.16);', 'border: 1px solid color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('border: 1px solid rgba(56, 189, 248, 0.35);', 'border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('border-color: rgba(56, 189, 248, 0.5);', 'border-color: color-mix(in srgb, var(--primary) 22%, transparent);'),
        ('border-color: rgba(56, 189, 248, 0.15);', 'border-color: color-mix(in srgb, var(--primary) 15%, transparent);'),
        ('border-color: rgba(56, 189, 248, 0.48);', 'border-color: color-mix(in srgb, var(--primary) 22%, transparent);'),
        ('border-color: rgba(56, 189, 248, 0.62);', 'border-color: color-mix(in srgb, var(--primary) 22%, transparent);'),
        ('border-top: 1px solid rgba(56,189,248,0.1);', 'border-top: 1px solid color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('border-bottom: 1px solid rgba(56,189,248,0.1);', 'border-bottom: 1px solid color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('border-right: 1px solid rgba(56,189,248,0.1);', 'border-right: 1px solid color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('border-right: none; border-bottom: 1px solid rgba(56,189,248,0.1);', 'border-right: none; border-bottom: 1px solid color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.25);', 'background:color-mix(in srgb, var(--primary) 12%, transparent);border:1px solid color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('background:rgba(245,158,11,0.08); border-color:rgba(245,158,11,0.2);', 'background:color-mix(in srgb, var(--warning) 8%, transparent); border-color:color-mix(in srgb, var(--warning) 15%, transparent);'),
        ('background:rgba(245,158,11,0.1); border-color:rgba(245,158,11,0.3);', 'background:color-mix(in srgb, var(--warning) 10%, transparent); border-color:color-mix(in srgb, var(--warning) 18%, transparent);'),
    ]
    for old_b, new_b in border_replacements:
        content = content.replace(old_b, new_b)

    # 5. Replacement for general hex references (case insensitive for 38bdf8, f59e0b)
    content = re.sub(r'#38[Bb][Dd][Ff]8', 'var(--primary)', content)
    content = re.sub(r'#FB923C', 'var(--warning)', content)
    content = re.sub(r'#fb923c', 'var(--warning)', content)
    content = re.sub(r'#F87171', 'var(--danger)', content)
    content = re.sub(r'#f87171', 'var(--danger)', content)
    content = re.sub(r'#ef4444', 'var(--danger)', content)
    content = re.sub(r'#EF4444', 'var(--danger)', content)
    content = re.sub(r'#f59e0b', 'var(--warning)', content)
    content = re.sub(r'#F59E0B', 'var(--warning)', content)

    # Also replace any remaining compact/standard rgba representations of blue/warning/danger
    # e.g., rgba(56, 189, 248, ...) and rgba(56,189,248,...)
    content = re.sub(
        r'rgba\(56,\s*189,\s*248,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--primary) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(56,189,248,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--primary) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    
    # Red rgba replacements
    content = re.sub(
        r'rgba\(239,\s*68,\s*68,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--danger) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(239,68,68,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--danger) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    
    # Orange/Amber rgba replacements
    content = re.sub(
        r'rgba\(251,\s*191,\s*36,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(245,\s*158,\s*11,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(245,158,11,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )

    return content

def update_dashboard_html(content):
    # SPECIFIC REPLACEMENTS FIRST (to prevent general regexes from breaking exact matching patterns)
    
    # Chart JS replacements
    content = content.replace(
        "const getLineColor = () => document.body.classList.contains('light-theme') ? '#2563eb' : '#38bdf8';",
        "const getLineColor = () => document.body.classList.contains('light-theme') ? '#0D9488' : '#2DD4BF';"
    )
    content = content.replace(
        "g.addColorStop(0, 'rgba(56, 189, 248, 0.24)');",
        "g.addColorStop(0, 'rgba(45, 212, 191, 0.24)');"
    )
    content = content.replace(
        "g.addColorStop(1, 'rgba(56, 189, 248, 0.00)');",
        "g.addColorStop(1, 'rgba(45, 212, 191, 0.00)');"
    )
    content = content.replace(
        "g.addColorStop(0, 'rgba(37, 99, 235, 0.22)');",
        "g.addColorStop(0, 'rgba(13, 148, 136, 0.22)');"
    )
    content = content.replace(
        "g.addColorStop(1, 'rgba(37, 99, 235, 0.00)');",
        "g.addColorStop(1, 'rgba(13, 148, 136, 0.00)');"
    )
    content = content.replace(
        "borderColor: document.body.classList.contains('light-theme') ? 'rgba(0,0,0,0.08)' : 'rgba(56, 189, 248, 0.25)',",
        "borderColor: document.body.classList.contains('light-theme') ? 'rgba(0,0,0,0.08)' : 'rgba(45, 212, 191, 0.25)',"
    )
    content = content.replace(
        "chart.options.plugins.tooltip.borderColor = document.body.classList.contains('light-theme') ? 'rgba(0,0,0,0.08)' : 'rgba(56, 189, 248, 0.25)';",
        "chart.options.plugins.tooltip.borderColor = document.body.classList.contains('light-theme') ? 'rgba(0,0,0,0.08)' : 'rgba(45, 212, 191, 0.25)';"
    )

    # Specific border replacements
    border_replacements = [
        ('border-color: rgba(56, 189, 248, 0.35); color: #38bdf8; background: rgba(56, 189, 248, 0.04);', 'border-color: color-mix(in srgb, var(--primary) 18%, transparent); color: var(--primary); background: color-mix(in srgb, var(--primary) 4%, transparent);'),
        ('border-color: rgba(56, 189, 248, 0.3);', 'border-color: color-mix(in srgb, var(--primary) 18%, transparent);'),
        ('background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.25);', 'background: color-mix(in srgb, var(--primary) 10%, transparent); border: 1px solid color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('onmouseover="this.style.borderColor=\'var(--primary)\'; this.style.background=\'rgba(56,189,248,0.04)\'"', 'onmouseover="this.style.borderColor=\'var(--primary)\'; this.style.background=\'color-mix(in srgb, var(--primary) 4%, transparent)\'"'),
    ]
    for old_b, new_b in border_replacements:
        content = content.replace(old_b, new_b)

    # Specific shadow replacements
    shadow_replacements = [
        ('box-shadow: 0 16px 40px rgba(56, 189, 248, 0.15) !important;', 'box-shadow: 0 16px 20px color-mix(in srgb, var(--primary) 9%, transparent) !important;'),
        ('box-shadow: 0 16px 40px rgba(37, 99, 235, 0.12) !important;', 'box-shadow: 0 16px 20px color-mix(in srgb, var(--primary) 8%, transparent) !important;'),
        ('box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);', 'box-shadow: 0 4px 7px color-mix(in srgb, var(--primary) 16%, transparent);'),
        ('box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);', 'box-shadow: 0 8px 10px color-mix(in srgb, var(--primary) 25%, transparent);'),
        ('box-shadow: 0 2px 6px rgba(59, 130, 246, 0.15);', 'box-shadow: 0 2px 4px color-mix(in srgb, var(--primary) 10%, transparent);'),
        ('box-shadow: 0 8px 24px rgba(37, 99, 235, 0.04) !important;', 'box-shadow: 0 8px 12px color-mix(in srgb, var(--primary) 4%, transparent) !important;'),
    ]
    for old_s, new_s in shadow_replacements:
        content = content.replace(old_s, new_s)

    # Red/danger replacements
    content = content.replace('var(--danger, #ef4444)', 'var(--danger)')
    content = content.replace('border: 1px solid rgba(239, 68, 68, 0.28);', 'border: 1px solid color-mix(in srgb, var(--danger) 18%, transparent);')
    content = content.replace('border: 1px solid rgba(239, 68, 68, 0.25);', 'border: 1px solid color-mix(in srgb, var(--danger) 16%, transparent);')
    content = content.replace('border-color: rgba(239, 68, 68, 0.2);', 'border-color: color-mix(in srgb, var(--danger) 15%, transparent);')
    content = content.replace('border-color: rgba(239, 68, 68, 0.3);', 'border-color: color-mix(in srgb, var(--danger) 18%, transparent);')
    content = content.replace('background: var(--danger-dim, rgba(239, 68, 68, 0.08));', 'background: var(--danger-dim);')

    # GENERAL REPLACEMENTS AT THE END
    
    # 1. Substitute #38bdf8 / #38BDF8 with var(--primary)
    content = re.sub(r'#38[Bb][Dd][Ff]8', 'var(--primary)', content)
    
    # 2. Replace hardcoded warning-adjacent orange #f59e0b / #F59E0B with var(--warning)
    content = content.replace('#f59e0b', 'var(--warning)')
    content = content.replace('#F59E0B', 'var(--warning)')
    
    # 3. Replace hardcoded red #ef4444 and #f87171 with var(--danger)
    content = re.sub(r'#[Ee][Ff]4444', 'var(--danger)', content)
    content = re.sub(r'#[Ff]87171', 'var(--danger)', content)
    
    # 4. Replace rgba(245, 158, 11, ...) with warning color-mix
    content = re.sub(
        r'rgba\(245,\s*158,\s*11,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    
    # 5. Red rgba replacements
    content = re.sub(
        r'rgba\(239,\s*68,\s*68,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--danger) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(239,68,68,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--danger) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )

    # 6. Compact and standard rgba representations of blue/warning/danger
    content = re.sub(
        r'rgba\(56,\s*189,\s*248,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--primary) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(56,189,248,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--primary) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    
    # Orange/Amber rgba replacements
    content = re.sub(
        r'rgba\(251,\s*191,\s*36,\s*([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )
    content = re.sub(
        r'rgba\(245,158,11,([\d\.]+)\)',
        lambda m: f'color-mix(in srgb, var(--warning) {float(m.group(1))*100:.1f}%, transparent)',
        content
    )

    return content

if __name__ == '__main__':
    # Update templates/home.html
    home_path = r'd:\Projects\Phishsim AI\Phishsim.ai-Core\templates\home.html'
    print("Reading templates/home.html...")
    with open(home_path, 'r', encoding='utf-8') as f:
        home_content = f.read()
    
    import subprocess
    print("Reverting files to clean git state first...")
    subprocess.run(['git', 'checkout', '--', home_path, r'd:\Projects\Phishsim AI\Phishsim.ai-Core\templates\dashboard.html'], check=True)
    
    with open(home_path, 'r', encoding='utf-8') as f:
        home_content = f.read()
        
    updated_home = update_home_html(home_content)
    
    print("Writing templates/home.html...")
    with open(home_path, 'w', encoding='utf-8') as f:
        f.write(updated_home)
        
    # Update templates/dashboard.html
    dash_path = r'd:\Projects\Phishsim AI\Phishsim.ai-Core\templates\dashboard.html'
    print("Reading templates/dashboard.html...")
    with open(dash_path, 'r', encoding='utf-8') as f:
        dash_content = f.read()
        
    updated_dash = update_dashboard_html(dash_content)
    
    print("Writing templates/dashboard.html...")
    with open(dash_path, 'w', encoding='utf-8') as f:
        f.write(updated_dash)
        
    print("Successfully finished styling update script.")
