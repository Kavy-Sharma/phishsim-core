import os

log_file = r'C:\Users\user\.gemini\antigravity-ide\brain\9a75e352-17d7-4d4c-bbe0-412be0e57d6e\.system_generated\logs\transcript_full.jsonl'
if os.path.exists(log_file):
    size = os.path.getsize(log_file)
    print(f'File size: {size} bytes')
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f'Line count: {len(lines)}')
        for i, line in enumerate(lines):
            if 'localStorage' in line or 'popover' in line or 'Prompt 2' in line:
                print(f'L{i+1}: {line[:200]}')
else:
    print('File does not exist')
