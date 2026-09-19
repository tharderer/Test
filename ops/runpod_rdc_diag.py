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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--password-file", required=True)
    args = ap.parse_args()

    password = Path(args.password_file).read_text().strip()
    s, xsrf = login(args.base, password)

    headers = {"X-XSRFToken": xsrf, "Referer": args.base + "/tree"}
    r = s.post(args.base + "/api/terminals", json={}, headers=headers, timeout=30)
    r.raise_for_status()
    term = r.json()["name"]

    ws_url = args.base.replace("https://", "wss://").replace("http://", "ws://") + f"/terminals/websocket/{term}"
    cookie = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
    ws = websocket.create_connection(ws_url, cookie=cookie, origin=args.base, timeout=30)

    remote_code = r'''
import json, os, pathlib, subprocess
ps = subprocess.check_output(["ps", "-eo", "pid,args"], text=True, errors="replace")

def count(substr):
    return sum(substr in line for line in ps.splitlines())

def exists(path):
    return pathlib.Path(path).exists()

def executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)

try:
    pid1 = pathlib.Path("/proc/1/cmdline").read_bytes().replace(bytes([0]), b" ").decode(errors="replace").strip()
except Exception as exc:
    pid1 = "ERROR:" + type(exc).__name__

diag = {
    "hostname": os.uname().nodename,
    "pid1_cmd": pid1,
    "rdc_entrypoint_exists": exists("/workspace/rdc-entrypoint.sh"),
    "rdc_entrypoint_executable": executable("/workspace/rdc-entrypoint.sh"),
    "pre_start_exists": exists("/workspace/pre_start_rdc.sh"),
    "pre_start_executable": executable("/workspace/pre_start_rdc.sh"),
    "auth_backup_exists": exists("/workspace/.rdc-auth-backup/device.json"),
    "rdc_agent_dir_exists": exists("/workspace/factory-runtime/rdc-agent"),
    "rdc_watchdog_processes": count("rdc-watchdog.sh"),
    "supervisor_processes": count("runpod-supervisor.sh"),
    "auth_sync_processes": count("rdc-auth-sync.sh"),
    "storage_monitor_processes": count("storage-quota-monitor.sh"),
    "comfy_watchdog_processes": count("comfy-watchdog.sh"),
    "desktop_commander_processes": sum(
        1 for line in ps.splitlines()
        if ("desktop-commander" in line.lower() or "/rdc-agent/" in line.lower())
    ),
}
print("__RDC_DIAG__" + json.dumps(diag, sort_keys=True), flush=True)
'''
    encoded = base64.b64encode(remote_code.encode()).decode()
    command = f"python3 -c \"import base64;exec(base64.b64decode('{encoded}'))\"\n"
    ws.send(json.dumps(["stdin", command]))

    deadline = time.time() + 30
    buf = ""
    diag = None
    while time.time() < deadline:
        raw = ws.recv()
        msg = json.loads(raw)
        if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "stdout":
            buf += msg[1]
            if "__RDC_DIAG__" in buf:
                tail = buf.split("__RDC_DIAG__", 1)[1]
                match = re.search(r"(\{.*?\})", tail, re.S)
                if match:
                    diag = json.loads(match.group(1))
                    break
    ws.close()

    try:
        s.delete(args.base + f"/api/terminals/{term}", headers=headers, timeout=10)
    except Exception:
        pass

    if diag is None:
        raise RuntimeError("Timed out waiting for RDC diagnostic marker")
    print(json.dumps(diag, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
