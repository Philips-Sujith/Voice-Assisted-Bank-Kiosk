"""
Python Environment Verifier & Safe Dependency Installer
Checks required dependencies for all Banking Kiosk microservices and installs missing items.
"""
import os
import sys
import subprocess
import importlib

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
    ("winsdk", "winsdk"),
    ("PIL", "pillow"),
    ("pypdf", "pypdf"),
    ("jinja2", "jinja2>=3.1.2"),
    ("markupsafe", "markupsafe>=2.0"),
]

OPTIONAL_HEAVY = [
    ("cv2", "opencv-python"),
    ("mediapipe", "mediapipe"),
    ("insightface", "insightface"),
    ("onnxruntime", "onnxruntime"),
]


def check_and_install():
    print("[Python Env] Verifying required Python dependencies...")
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
            cmd = [sys.executable, "-m", "pip", "install", pkg_name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[ERROR] Failed to install {pkg_name}:")
                print(res.stderr)
                sys.exit(1)
            print(f"  [OK] {pkg_name} installed successfully.")
    else:
        print("[Python Env] Core dependencies are satisfied.")

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
            cmd = [sys.executable, "-m", "pip", "install", pkg_name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[ERROR] Failed to install {pkg_name}:")
                print(res.stderr)
                sys.exit(1)
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
