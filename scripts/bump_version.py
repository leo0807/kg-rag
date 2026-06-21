#!/usr/bin/env python3
"""Update version strings in config.py, package.json, and SidebarFooter.tsx."""
import re
import sys

if len(sys.argv) != 2:
    print("Usage: bump_version.py <new_version>")
    sys.exit(1)

version = sys.argv[1].lstrip("v")

files = [
    ("backend/src/core/config.py", r'APP_VERSION:\s*str\s*=\s*"[^"]+"', f'APP_VERSION:  str = "{version}"'),
    ("frontend/package.json", r'"version":\s*"[^"]+"', f'"version": "{version}"'),
    (
        "frontend/src/app/sidebar/SidebarFooter.tsx",
        r'v\d+\.\d+\.\d+',
        f'v{version}',
    ),
]

for path, pattern, replacement in files:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    updated = re.sub(pattern, replacement, content)
    if updated != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"Updated {path}")
    else:
        print(f"No change in {path}")
