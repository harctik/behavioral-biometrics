import os
import re

src_dir = r"d:\Behavior-Based-Authentication-main\frontend\src"

def process_file(filepath):
    if "auth-utils.ts" in filepath: return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    orig_content = content
    content = re.sub(r'document\.cookie\??\.match\(/csrf_access_token=\(\[\^;\]\+\)/\)\?\.\[1\](\s*\|\|\s*"")?', 'getCsrfToken()', content)
    content = re.sub(r'document\.cookie\??\.match\(/session_id=\(\[\^;\]\+\)/\)\?\.\[1\](\s*\|\|\s*"")?', 'getSessionId()', content)

    if content != orig_content:
        imports_needed = []
        if "getCsrfToken()" in content and "getCsrfToken" not in orig_content:
            imports_needed.append("getCsrfToken")
        if "getSessionId()" in content and "getSessionId" not in orig_content:
            imports_needed.append("getSessionId")
            
        if imports_needed:
            # check if auth-utils is already imported
            if "auth-utils" not in content:
                import_stmt = f'import {{ {", ".join(["getCsrfToken", "getSessionId"])} }} from "@/lib/auth-utils";\n'
                # insert after "use client"; if exists, else top
                if content.startswith('"use client";'):
                    content = content.replace('"use client";', '"use client";\n' + import_stmt, 1)
                elif content.startswith("'use client';"):
                    content = content.replace("'use client';", "'use client';\n" + import_stmt, 1)
                else:
                    content = import_stmt + content
            else:
                # it has auth-utils import, maybe we should manually fix those files if any issue.
                # Actually, let's just insert the new ones if not present in the regex
                pass

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith(".ts") or f.endswith(".tsx"):
            process_file(os.path.join(root, f))
