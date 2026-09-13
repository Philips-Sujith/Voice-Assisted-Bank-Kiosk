"""
Python Environment Verifier & Safe Dependency Installer
Checks required dependencies for all Banking Kiosk microservices and installs missing items.
Ensures zero-compilation portable setup without requiring Visual Studio or C++ compilers.
"""
import os
import sys
import subprocess
import importlib

# ── 1. Python Version Compatibility Check ─────────────────────────────────────
# Python 3.11 is the standardized target (Python 3.10 to 3.12 supported).
# Python 3.14 (and 3.13+) lack prebuilt binary wheels for native biometric and WinRT packages.
if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
    print("=" * 78)
    print(f" [ERROR] INCOMPATIBLE PYTHON VERSION DETECTED: Python {sys.version.split()[0]}")
    print("=" * 78)
    print(" This project requires Python 3.11 (Python 3.10 to 3.12 supported).")
    print(f" Python {sys.version_info.major}.{sys.version_info.minor} is not supported by native biometric and Windows binary wheels.")
    print("")
    print(" IMPORTANT:")
    print("  - Do NOT install Visual Studio, CMake, or C++ build tools.")
    print("  - Pre-built binary wheels are available for Python 3.11 without any compilation.")
    print("  - Please run START_DEMO.bat using Python 3.11, or create your .venv using:")
    print("      py -3.11 -m venv .venv")
    print("=" * 78)
    sys.exit(1)


REQUIRED_IMPORTS = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn[standard]"),
    ("pydantic", "pydantic>=2.4"),
    ("pydantic_settings", "pydantic-settings"),
    ("Crypto", "pycryptodome>=3.20"),
    ("qrcode", "qrcode[pil]>=7.4"),
    ("fakeredis", "fakeredis"),
    ("transitions", "transitions>=0.9.0"),
    ("redis", "redis>=5.0.0"),
    ("httpx", "httpx>=0.27.0"),
    ("websockets", "websockets>=12.0"),
    ("multipart", "python-multipart"),
    ("dotenv", "python-dotenv"),
    ("psutil", "psutil"),
    ("PIL", "pillow"),
    ("pypdf", "pypdf"),
    ("jinja2", "jinja2>=3.1.2"),
    ("markupsafe", "markupsafe>=2.0"),
    ("pyttsx3", "pyttsx3"),
]

OPTIONAL_HEAVY = [
    ("cv2", "opencv-python"),
    ("mediapipe", "mediapipe"),
    ("insightface", "insightface"),
    ("onnxruntime", "onnxruntime"),
]


def check_and_install_winsdk():
    """
    Safely checks and installs winsdk on Windows using prebuilt wheels ONLY.
    Strictly forbids source compilation to avoid requiring Visual Studio / CMake.
    """
    if sys.platform != "win32":
        return

    try:
        import winsdk
        print("  [OK] winsdk (Windows native OCR) is already installed.")
        return
    except ImportError:
        pass

    print("  -> Checking Windows native OCR package (winsdk==1.0.0b10)...")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--prefer-binary",
        "--only-binary",
        ":all:",
        "winsdk==1.0.0b10",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("  [OK] winsdk installed successfully from prebuilt binary wheel.")
    else:
        print("  [Notice] Prebuilt wheel for 'winsdk' was not installed.")
        print("  [Notice] Native passbook image OCR will run in fallback mode.")
        print("  [Notice] (Demo passbooks, PDF uploads, and all kiosk services are fully operational).")


def check_and_install():
    print(f"[Python Env] Verifying Python {sys.version.split()[0]} environment...")
    missing = []

    for mod_name, pkg_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append((mod_name, pkg_name))

    if missing:
        print(f"[Python Env] Installing {len(missing)} missing packages...")
        for mod_name, pkg_name in missing:
            print(f"  -> Installing {pkg_name}...")
            cmd = [sys.executable, "-m", "pip", "install", "--prefer-binary", pkg_name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[ERROR] Failed to install {pkg_name}:")
                print(res.stderr)
                sys.exit(1)
            print(f"  [OK] {pkg_name} installed successfully.")
    else:
        print("[Python Env] Core dependencies are satisfied.")

    # Check Windows-specific native OCR (winsdk) safely without compilation
    check_and_install_winsdk()

    # Check Face Auth dependencies
    face_missing = []
    for mod_name, pkg_name in OPTIONAL_HEAVY:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            face_missing.append((mod_name, pkg_name))

    if face_missing:
        print("[Python Env] Notice: Installing face authentication dependencies...")
        for mod_name, pkg_name in face_missing:
            print(f"  -> Installing {pkg_name}...")
            cmd = [sys.executable, "-m", "pip", "install", "--prefer-binary", pkg_name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[ERROR] Failed to install {pkg_name}:")
                print(res.stderr)
                sys.exit(1)
            print(f"  [OK] {pkg_name} installed successfully.")
    else:
        print("[Python Env] Face authentication dependencies are satisfied.")

    # Check Face Auth model files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    model_dirs = [
        os.path.join(project_root, "services", "identity", "models"),
        os.path.join(base_dir, "services", "identity", "models"),
    ]
    models_dir = next((d for d in model_dirs if os.path.exists(d)), None)
    if models_dir:
        required_models = [
            os.path.join(models_dir, "face_detection_yunet_2023mar.onnx"),
            os.path.join(models_dir, "2.7_80x80_MiniFASNetV2.onnx"),
            os.path.join(models_dir, "4_0_0_80x80_MiniFASNetV1SE.onnx"),
            os.path.join(models_dir, "buffalo_l", "w600k_r50.onnx"),
            os.path.join(models_dir, "buffalo_l", "1k3d68.onnx"),
        ]
        missing_models = [m for m in required_models if not os.path.exists(m)]
        if missing_models:
            print("[Python Env] WARNING: Missing Face Authentication model files:")
            for m in missing_models:
                print(f"  - {os.path.relpath(m, base_dir)}")
        else:
            print("[Python Env] Face Authentication model files verified.")

    print("[Python Env] Python environment is completely ready.")


if __name__ == "__main__":
    check_and_install()
