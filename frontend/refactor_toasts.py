import os
import re
import glob

def process_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Add import
    if "import { toast } from \"sonner\";" not in content and "setError(" in content:
        content = re.sub(r'(import .*?;)', r'\1\nimport { toast } from "sonner";', content, count=1)

    # Remove state declarations
    content = re.sub(r'const\s+\[error,\s*setError\]\s*=\s*useState<[^>]*>\([^)]*\);', '', content)
    content = re.sub(r'const\s+\[error,\s*setError\]\s*=\s*useState\([^)]*\);', '', content)
    content = re.sub(r'const\s+\[successMsg,\s*setSuccessMsg\]\s*=\s*useState\([^)]*\);', '', content)
    content = re.sub(r'const\s+\[message,\s*setMessage\]\s*=\s*useState\([^)]*\);', '', content)

    # Replace empty setters
    content = re.sub(r'setError\(\"\"?\)', '', content)
    content = re.sub(r'setSuccessMsg\(\"\"?\)', '', content)
    content = re.sub(r'setMessage\(\"\"?\)', '', content)
    
    # Replace actual setters with toast
    content = re.sub(r'setError\((.*?)\);', r'toast.error(\1);', content)
    content = re.sub(r'setSuccessMsg\((.*?)\);', r'toast.success(\1);', content)
    content = re.sub(r'setMessage\((.*?)\);', r'toast.success(\1);', content)

    # Remove inline AuthInlineMessage components
    content = re.sub(r'\{error\s*\?\s*<AuthInlineMessage[^>]*>.*?</AuthInlineMessage>\s*:\s*null\}', '', content, flags=re.DOTALL)
    content = re.sub(r'\{message\s*\?\s*<AuthInlineMessage[^>]*>.*?</AuthInlineMessage>\s*:\s*null\}', '', content, flags=re.DOTALL)

    # Remove the specific block from login
    block = r'\{error && \(\s*<motion\.div[^>]*>.*?\{error\}\s*</motion\.div>\s*\)\}'
    content = re.sub(block, '', content, flags=re.DOTALL)

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Refactored {filepath}")

for f in glob.glob("src/app/**/*.tsx", recursive=True):
    process_file(f)
