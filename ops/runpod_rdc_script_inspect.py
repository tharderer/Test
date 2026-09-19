#!/usr/bin/env python3
import argparse
import base64
import re
from pathlib import Path

import requests


def login(base: str, password: str):
    s = requests.Session()
    r = s.get(base + "/login", timeout=30)
    r.raise_for_status()
    xsrf = s.cookies.get("_xsrf")
    if not xsrf:
        m = re.search(r'name=["\']_xsrf["\']\s+value=["\']([^"\']+)', r.text)
        xsrf = m.group(1) if m else None
    if not xsrf:
        raise RuntimeError("No Jupyter XSRF token")
    r = s.post(
        base + "/login?next=%2Ftree",
        data={"_xsrf": xsrf, "password": password},
        headers={"Referer": base + "/login"},
        allow_redirects=False,
        timeout=30,
    )
    if r.status_code not in (302, 303) or "/login" in r.headers.get("Location", ""):
        raise RuntimeError("Jupyter authentication failed")
    return s


def read_text(s, base, path):
    r = s.get(base + "/api/contents/" + path + "?content=1", timeout=30)
    r.raise_for_status()
    j = r.json()
    content = j.get("content") or ""
    if j.get("format") == "base64":
        return base64.b64decode(content).decode(errors="replace")
    return content


def sanitize(line):
    if re.search(r'password|token|secret|authorization|api[_ -]?key', line, re.I):
        return None
    line = re.sub(r'([A-Za-z0-9_-]{40,})', '***', line)
    return line[:1000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--password-file", required=True)
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    s = login(args.base, password)

    paths = [
        "workspace/rdc-entrypoint.sh",
        "workspace/pre_start_rdc.sh",
        "workspace/rdc-watchdog.sh",
        "workspace/rdc-auth-sync.sh",
        "workspace/runpod-supervisor.sh",
    ]
    wanted = re.compile(r'rdc|desktop|device|auth|watchdog|log|node|npm|npx|HOME|config|factory-runtime|nohup|pid', re.I)

    for path in paths:
        print(f"--- {path} relevant lines ---")
        try:
            text = read_text(s, args.base, path)
        except Exception as exc:
            print("READ_FAILED", type(exc).__name__)
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if wanted.search(line):
                safe = sanitize(line)
                if safe is not None:
                    print(f"{i}: {safe}")


if __name__ == "__main__":
    main()
