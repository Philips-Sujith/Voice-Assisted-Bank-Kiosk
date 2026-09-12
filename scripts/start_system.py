"""
Unified Orchestration Launcher for AI Voice-Assisted Banking Kiosk
Starts and monitors all 6 backend/frontend services + Redis Broker.
Fully portable across Windows paths, drives, and directory names (including spaces).

Port Mapping:
- Redis Broker:                  6379
- Customer Kiosk:                5173
- Voice Service:                 8002
- Banking API:                   8000
- Identity & Biometrics Service: 8003
- Security Service:              8001
- Teller Portal:                 5174
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CURRENT_FILE = Path(__file__).resolve()
if CURRENT_FILE.parent.name == "scripts":
    PROJECT_ROOT = CURRENT_FILE.parent.parent
else:
    PROJECT_ROOT = CURRENT_FILE.parent

KIOSK_ROOT = PROJECT_ROOT / "apps" / "customer-kiosk"
TELLER_ROOT = PROJECT_ROOT / "apps" / "teller-portal"
BANKING_ROOT = PROJECT_ROOT / "services" / "banking-api"
IDENTITY_ROOT = PROJECT_ROOT / "services" / "identity"
SECURITY_ROOT = PROJECT_ROOT / "services" / "security"
VOICE_ROOT = PROJECT_ROOT / "services" / "voice"
REDIS_SCRIPT = PROJECT_ROOT / "infrastructure" / "redis" / "run_redis.py"



NPM_BIN = shutil.which("npm.cmd") or shutil.which("npm") or "npm"

SERVICES = [
    {
        "name": "Redis Broker",
        "cmd": [sys.executable, str(REDIS_SCRIPT)],
        "cwd": str(PROJECT_ROOT),
        "port": 6379,
        "type": "tcp",
    },
    {
        "name": "Security Service",
        "cmd": [sys.executable, "app.py"],
        "cwd": str(SECURITY_ROOT),
        "port": 8001,
        "url": "http://127.0.0.1:8001/health",
        "type": "http",
    },
    {
        "name": "Identity & Biometrics Service",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],
        "cwd": str(IDENTITY_ROOT),
        "port": 8003,
        "url": "http://127.0.0.1:8003/health",
        "type": "http",
    },
    {
        "name": "Banking Core API",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(BANKING_ROOT),
        "port": 8000,
        "url": "http://127.0.0.1:8000/docs",
        "type": "http",
    },
    {
        "name": "Voice Interaction Service",
        "cmd": [sys.executable, "server.py"],
        "cwd": str(VOICE_ROOT),
        "port": 8002,
        "url": "http://127.0.0.1:8002/health",
        "type": "http",
    },
    {
        "name": "Teller Portal",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(TELLER_ROOT),
        "port": 5174,
        "url": "http://localhost:5174",
        "type": "http",
    },
    {
        "name": "Customer Kiosk",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(KIOSK_ROOT),
        "port": 5173,
        "url": "http://localhost:5173",
        "type": "http",
    },
]


def is_port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def check_health(svc: dict) -> bool:
    if svc["type"] == "tcp":
        return is_port_in_use(svc["port"])
    elif svc["type"] == "http":
        try:
            req = urllib.request.Request(svc["url"], headers={"User-Agent": "BankingKioskHealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 301, 302, 307)
        except Exception:
            return False
    return False


def main():
    print("=" * 66)
    print("      NEXA BANKING KIOSK SYSTEM — UNIFIED ORCHESTRATOR           ")
    print("=" * 66)

    procs: list[tuple[dict, subprocess.Popen]] = []

    def cleanup(sig=None, frame=None):
        print("\n\n[Shutting down all banking kiosk services...]")
        for svc, p in procs:
            if p.poll() is None:
                p.terminate()
        time.sleep(1)
        for svc, p in procs:
            if p.poll() is None:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]

        if is_port_in_use(port):
            print(f"[Notice] Port {port} for {name} is already active. Skipping duplicate launch.")
            continue

        print(f"[Starting] {name} on port {port}...")
        first_arg = str(svc["cmd"][0]).lower()
        is_cmd = sys.platform == "win32" and (
            first_arg.endswith(".cmd")
            or first_arg.endswith(".bat")
            or "npm" in first_arg
        )
        p = subprocess.Popen(
            svc["cmd"],
            cwd=svc["cwd"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=is_cmd,
        )
        procs.append((svc, p))

    print("\n[Orchestrator] Waiting for all services to become healthy...")
    time.sleep(2)

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        healthy = False

        for _ in range(25):
            if check_health(svc):
                healthy = True
                break
            time.sleep(1)

        if healthy:
            print(f"  [OK]   {name.ljust(30)} -> ONLINE on port {port}")
        else:
            print(f"  [FAIL] {name.ljust(30)} -> FAILED / TIMED OUT on port {port}")

    print("\n[Orchestrator] All services launched! System is live.")
    print("  Customer Kiosk:  http://localhost:5173")
    print("  Face Enrollment: http://localhost:5173/#/face-enrollment")
    print("  Teller Portal:   http://localhost:5174")
    print("  Backend API:     http://localhost:8000/docs")
    print("  Voice AI WS:     ws://localhost:8002/ws/audio")
    print("Press Ctrl+C to terminate all services.\n")

    try:
        while True:
            time.sleep(2)
            for svc, p in procs:
                ret = p.poll()
                if ret is not None:
                    print(f"[ALERT] {svc['name']} exited unexpectedly with code {ret}!")
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
