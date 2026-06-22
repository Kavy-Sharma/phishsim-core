with open('static/style.css', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'overflow' in line:
            safe_line = line.strip().encode('ascii', errors='ignore').decode('ascii')
            print(f'{i+1}: {safe_line}')
