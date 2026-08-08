with open('scratch/home_curl_fresh.html', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'selectSandboxScenario(' in line or 'class ToolMiniLoader' in line:
            print(f'{i+1}: {line.strip()[:100]}')
