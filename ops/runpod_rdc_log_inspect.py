#!/usr/bin/env python3
import argparse
import base64
import re
from pathlib import Path
import requests

SENSITIVE = re.compile(
    r'password|authorization|api[_ -]?key|secret|bearer|access[_ -]?token|refresh[_ -]?token',
    re.I,
)

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
    print(f"{path} HTTP: {r.status_code}")
    if r.status_code != 200:
        return ""
    j = r.json()
    content = j.get("content") or ""
    if j.get("format") == "base64":
        return base64.b64decode(content).decode(errors="replace")
    return content

def sanitize(line: str):
    if SENSITIVE.search(line):
        return "[REDACTED SENSITIVE LINE]"
    line = re.sub(r'(?i)(bearer\s+)[^\s]+', r'\1***', line)
    line = re.sub(r'\b[A-Za-z0-9._~+/=-]{40,}\b', '***', line)
    line = re.sub(r'(?i)(https?://[^\s?]+)\?[^\s]+', r'\1?[REDACTED_QUERY]', line)
    return line[:1500]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--password-file", required=True)
    args = ap.parse_args()

    password = Path(args.password_file).read_text().strip()
    s = login(args.base, password)

    for path in (
        "workspace/logs/rdc-agent.log",
        "workspace/logs/rdc-auth-sync.log",
        "workspace/logs/runpod-supervisor.log",
    ):
        text = read_text(s, args.base, path)
        lines = text.splitlines()
        print(f"--- {path}: {len(lines)} lines; sanitized tail ---")
        for line in lines[-120:]:
            print(sanitize(line))

if __name__ == "__main__":
    main()
