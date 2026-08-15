import os
import re

patterns = [
    re.compile(r'(<form[^>]*method=["\']?post["\']?[^>]*>)', re.IGNORECASE)
]

templates_dir = "templates"

modified_files = []

for root, dirs, files in os.walk(templates_dir):
    for file in files:
        if file.endswith(".html"):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            
            new_content = content
            # Let's find matches and replace them
            # We want to insert the token right after the tag
            # But avoid inserting it multiple times if it's already there (for idempotency)
            def replace_form(match):
                form_tag = match.group(1)
                # Check if csrf_token is already present immediately after this form tag (ignoring whitespace)
                # Find the start index of form_tag in new_content to check what follows it
                # But since we use re.sub, we can just check if "{{ csrf_token() }}" is already in form_tag or nearby
                return form_tag + '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">'
            
            # Simple check: if "{{ csrf_token() }}" is already present in the file near a form, we might skip or handle it.
            # But let's check if the file already has csrf_token.
            # Since we just added it to base.html head, base.html will have it in the head but not in a form (base.html has no POST form).
            # Let's count how many POST forms the file has and how many csrf_tokens it has.
            # If the file has no POST forms, we don't modify it.
            forms = patterns[0].findall(content)
            if not forms:
                continue
                
            # If any forms exist, let's replace them, but let's be careful not to double-inject.
            # We can use a regex that matches `<form...>` but ONLY if it is not already followed by the csrf_token input.
            # A negative lookahead: `(?!.*name=["\']csrf_token["\'])` is tricky because of arbitrary content in between.
            # Let's do a clean replacement by checking if the csrf_token is already present in the file's forms.
            # If the file already contains `<input type="hidden" name="csrf_token"`, we skip to avoid double injection.
            if 'name="csrf_token"' in content or "name='csrf_token'" in content:
                print(f"Skipping {file_path} - CSRF token already present.")
                continue
                
            new_content = patterns[0].sub(replace_form, content)
            
            if new_content != content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                modified_files.append(file_path)

print(f"Successfully processed templates. Modified {len(modified_files)} files:")
for f in modified_files:
    print(f" - {f}")
