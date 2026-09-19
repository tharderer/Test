#!/usr/bin/env python3
import argparse
import base64
import json
import re
import time
from pathlib import Path

import requests
import websocket


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
    return s, xsrf


def run_terminal(s, xsrf, base, shell_script):
    headers = {"X-XSRFToken": xsrf, "Referer": base + "/tree"}
    r = s.post(base + "/api/terminals", json={}, headers=headers, timeout=30)
    r.raise_for_status()
    term = r.json()["name"]
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + f"/terminals/websocket/{term}"
    cookie = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
    ws = websocket.create_connection(ws_url, cookie=cookie, origin=base, timeout=30)

    marker = "__RDC_REPAIR_DONE__"
    payload = base64.b64encode(shell_script.encode()).decode()
    command = f"python3 -c \"import base64,subprocess; s=base64.b64decode('{payload}').decode(); rc=subprocess.call(['/bin/bash','-lc',s]); print('{marker}'+str(rc), flush=True)\"\n"
    ws.send(json.dumps(["stdin", command]))

    deadline = time.time() + 300
    buf = ""
    rc = None
    safe_lines = []
    while time.time() < deadline:
        try:
            raw = ws.recv()
        except Exception:
            continue
        msg = json.loads(raw)
        if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "stdout":
            chunk = msg[1]
            buf += chunk
            for line in chunk.splitlines():
                if marker not in line:
                    if re.search(r'password|token|secret|authorization|api[_ -]?key', line, re.I):
                        safe_lines.append("[REDACTED SENSITIVE OUTPUT]")
                    else:
                        safe_lines.append(re.sub(r'\b[A-Za-z0-9._~+/=-]{40,}\b', '***', line)[:1200])
            if marker in buf:
                tail = buf.rsplit(marker, 1)[1]
                m = re.match(r'(\d+)', tail.strip())
                if m:
                    rc = int(m.group(1))
                    break

    ws.close()
    try:
        s.delete(base + f"/api/terminals/{term}", headers=headers, timeout=10)
    except Exception:
        pass

    for line in safe_lines[-120:]:
        print(line)
    if rc is None:
        raise RuntimeError("Timed out waiting for repair completion")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--password-file", required=True)
    args = ap.parse_args()

    password = Path(args.password_file).read_text().strip()
    s, xsrf = login(args.base, password)

    shell_script = r'''
set -euo pipefail
NODE_ROOT=/workspace/factory-runtime/node
RDC_ROOT=/workspace/factory-runtime/rdc-agent
TMP_ROOT="$(mktemp -d /workspace/factory-runtime/.node-repair.XXXXXX)"
cleanup(){ rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) node_arch=linux-x64 ;;
  aarch64|arm64) node_arch=linux-arm64 ;;
  *) echo "Unsupported architecture: $arch"; exit 20 ;;
esac

echo "Downloading Node.js LTS metadata..."
curl -fsSL https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt -o "$TMP_ROOT/SHASUMS256.txt"
tarname="$(awk -v a="$node_arch" '$2 ~ a "\\.tar\\.xz$" {print $2; exit}' "$TMP_ROOT/SHASUMS256.txt")"
test -n "$tarname"

echo "Downloading checksum-pinned Node.js archive: $tarname"
curl -fsSL "https://nodejs.org/dist/latest-v22.x/$tarname" -o "$TMP_ROOT/$tarname"
(
  cd "$TMP_ROOT"
  grep "  $tarname$" SHASUMS256.txt | sha256sum -c -
)

echo "Installing persistent Node runtime..."
tar --no-same-owner -xJf "$TMP_ROOT/$tarname" -C "$TMP_ROOT"
extracted="$TMP_ROOT/${tarname%.tar.xz}"
rm -rf "${NODE_ROOT}.new"
mv "$extracted" "${NODE_ROOT}.new"
if [ -e "$NODE_ROOT" ] || [ -L "$NODE_ROOT" ]; then
  backup="${NODE_ROOT}.pre-repair.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$NODE_ROOT" "$backup"
  echo "Previous Node path preserved at $(basename "$backup")"
fi
mv "${NODE_ROOT}.new" "$NODE_ROOT"

export PATH="$NODE_ROOT/bin:$PATH"
echo "Node: $("$NODE_ROOT/bin/node" --version)"
echo "npm: $("$NODE_ROOT/bin/npm" --version)"

echo "Installing pinned Desktop Commander 0.2.51..."
mkdir -p "$RDC_ROOT"
cd "$RDC_ROOT"
if [ ! -f package.json ]; then
  "$NODE_ROOT/bin/npm" init -y >/dev/null 2>&1
fi
"$NODE_ROOT/bin/npm" install --no-audit --no-fund --save-exact @wonderwhy-er/desktop-commander@0.2.51

test -x "$RDC_ROOT/node_modules/.bin/desktop-commander"
test -f "$RDC_ROOT/node_modules/@wonderwhy-er/desktop-commander/dist/index.js"

echo "Desktop Commander persistent install: PASS"
echo "Existing watchdog will retry automatically."
'''
    rc = run_terminal(s, xsrf, args.base, shell_script)
    print("RDC repair exit code:", rc)
    if rc != 0:
        raise SystemExit(rc)


if __name__ == "__main__":
    main()
