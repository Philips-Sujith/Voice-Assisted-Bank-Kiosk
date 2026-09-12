"""
Unified Multi-Module Orchestration Launcher
Starts and monitors all 6 services + Redis Broker for the Voice-Assisted Banking Kiosk System.
Fully portable across Windows paths, drives, and directory names (including spaces).

Port Mapping:
- Redis Broker:           6379
- Module 1 (Kiosk):       5173
- Module 2 (Voice AI):    8002
- Module 3 (Backend):     8000
- Module 4 (Face Auth):   8003
- Module 5 (Security QR): 8001
- Module 6 (Staff Portal):5174
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

ROOT = Path(__file__).resolve().parent

if (ROOT / "AI-Based-Voice-Assisted-Kiosk-Prototype").exists():
    REPO_ROOT = ROOT / "AI-Based-Voice-Assisted-Kiosk-Prototype"
else:
    REPO_ROOT = ROOT

if (ROOT / "module-repos" / "Gopika_Module").exists():
    KIOSK_ROOT = ROOT / "module-repos" / "Gopika_Module"
elif (ROOT.parent / "module-repos" / "Gopika_Module").exists():
    KIOSK_ROOT = ROOT.parent / "module-repos" / "Gopika_Module"
elif (REPO_ROOT / "module1_customer_kiosk").exists():
    KIOSK_ROOT = REPO_ROOT / "module1_customer_kiosk"
else:
    KIOSK_ROOT = ROOT / "module-repos" / "Gopika_Module"

STAFF_ROOT = REPO_ROOT / "module6_staff_portal"

NPM_BIN = shutil.which("npm.cmd") or shutil.which("npm") or "npm"

SERVICES = [
    {
        "name": "Redis Broker",
        "cmd": [sys.executable, str(ROOT / "run_redis.py")],
        "cwd": str(ROOT),
        "port": 6379,
        "type": "tcp",
    },
    {
        "name": "Module 5: Security QR",
        "cmd": [sys.executable, "app.py"],
        "cwd": str(REPO_ROOT / "module5_security"),
        "port": 8001,
        "url": "http://127.0.0.1:8001/health",
        "type": "http",
    },
    {
        "name": "Module 4: Face Auth",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],
        "cwd": str(REPO_ROOT / "module4_face_auth"),
        "port": 8003,
        "url": "http://127.0.0.1:8003/health",
        "type": "http",
    },
    {
        "name": "Module 3: Central Backend",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(REPO_ROOT / "module3_backend"),
        "port": 8000,
        "url": "http://127.0.0.1:8000/docs",
        "type": "http",
    },
    {
        "name": "Module 2: Voice AI",
        "cmd": [sys.executable, "server.py"],
        "cwd": str(REPO_ROOT / "module2_voice"),
        "port": 8002,
        "url": "http://127.0.0.1:8002/health",
        "type": "http",
    },
    {
        "name": "Module 6: Staff Portal",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(STAFF_ROOT),
        "port": 5174,
        "url": "http://localhost:5174",
        "type": "http",
    },
    {
        "name": "Module 1: Customer Kiosk",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(KIOSK_ROOT),
        "port": 5173,
        "url": "http://localhost:5173",
        "type": "http",
    },
]

processes: list[tuple[dict, subprocess.Popen]] = []


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
            req = urllib.request.Request(svc["url"], headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 301, 302, 307)
        except Exception:
            return False
    return False


def cleanup(sig=None, frame=None):
    print("\n[Orchestrator] Shutting down all services...")
    for svc, proc in reversed(processes):
        print(f"[Orchestrator] Terminating {svc['name']} (PID {proc.pid})...")
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print("[Orchestrator] All services shut down successfully.")
    sys.exit(0)


def start_all():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("==================================================================")
    print("      NEXA BANKING KIOSK SYSTEM — UNIFIED ORCHESTRATOR           ")
    print("==================================================================")

    runtime_dir = ROOT / "runtime"
    logs_dir = runtime_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]

        if is_port_in_use(port):
            print(f"[OK] {name} is already active on port {port}.")
            continue

        print(f"[Starting] {name} on port {port}...")
        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        log_file = open(logs_dir / f"{safe_name}.log", "a", encoding="utf-8")
        try:
            first_arg = str(svc["cmd"][0]).lower()
            is_cmd = sys.platform == "win32" and (
                first_arg.endswith(".cmd")
                or first_arg.endswith(".bat")
                or "npm" in first_arg
            )
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=svc["cwd"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=is_cmd,
            )
            processes.append((svc, proc))
        except Exception as exc:
            print(f"[ERROR] Failed to start {name}: {exc}")

    # Health check wait loop
    print("\n[Orchestrator] Waiting for all services to become healthy...")
    time.sleep(3)

    all_healthy = True
    proc_map = {svc["name"]: proc for svc, proc in processes}

    for svc in SERVICES:
        name = svc["name"]
        proc = proc_map.get(name)
        healthy = False
        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")

        for _ in range(15):
            if proc and proc.poll() is not None:
                break
            if check_health(svc):
                healthy = True
                break
            time.sleep(1)

        if healthy:
            print(f"  [OK]   {name.ljust(28)} -> ONLINE on port {svc['port']}", flush=True)
        else:
            all_healthy = False
            if proc and proc.poll() is not None:
                print(f"  [FAIL] {name.ljust(28)} -> EXITED (Code {proc.poll()})", flush=True)
                print(f"         Log: runtime/logs/{safe_name}.log", flush=True)
            else:
                print(f"  [!]    {name.ljust(28)} -> INITIALIZING / PENDING on port {svc['port']}", flush=True)

    if all_healthy:
        print("\n[Orchestrator] All services launched! System is live.", flush=True)
    else:
        print("\n[Orchestrator] Notice: One or more services failed or exited.", flush=True)

    print("  Customer Kiosk:  http://localhost:5173", flush=True)
    print("  Face Enrollment: http://localhost:5173/#/face-enrollment", flush=True)
    print("  Staff Portal:    http://localhost:5174", flush=True)
    print("  Backend API:     http://localhost:8000/docs", flush=True)
    print("  Voice AI WS:     ws://localhost:8002/ws/audio", flush=True)
    print("Press Ctrl+C to terminate all services.\n", flush=True)

    reported_exits = set()
    try:
        while True:
            time.sleep(1)
            for svc, proc in processes:
                poll = proc.poll()
                if poll is not None and svc["name"] not in reported_exits:
                    reported_exits.add(svc["name"])
                    safe_name = "".join(c if c.isalnum() else "_" for c in svc["name"].lower()).strip("_")
                    print(f"\n[ALERT] {svc['name']} exited with code {poll}!", flush=True)
                    print(f"        Log: runtime/logs/{safe_name}.log\n", flush=True)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    start_all()
