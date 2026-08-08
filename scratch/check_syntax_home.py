import re
import subprocess
import tempfile

with open('templates/home.html', 'r', encoding='utf-8') as f:
    content = f.read()

scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)

for i, script in enumerate(scripts):
    print(f'Checking Script Block #{i+1} ({len(script)} chars)...')
    with tempfile.NamedTemporaryFile(suffix='.js', delete=False, mode='w', encoding='utf-8') as tmp:
        tmp.write(script)
        tmp_name = tmp.name
    
    try:
        res = subprocess.run(['node', '--check', tmp_name], capture_output=True, text=True)
        if res.returncode != 0:
            print(f'Block #{i+1} has syntax errors:')
            print(res.stderr)
        else:
            print(f'Block #{i+1} is syntax-valid.')
    except Exception as e:
        print(f'Failed to check Block #{i+1}: {e}')
