"""FileNest Backend Packaging Script (PyInstaller)

Supports:
  --mode=full : Opsi A - Bundles PaddleOCR PP-OCRv4 models for 100% offline usage.
  --mode=lite : Opsi B - Lightweight bundle without pre-packaged OCR models.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DIST_DIR = PROJECT_ROOT / "dist_backend"
SRC_TAURI_RESOURCES = PROJECT_ROOT / "src-tauri" / "resources" / "backend"

def run_pyinstaller(mode: str):
    print("=" * 60)
    print(f"  Building FileNest Backend - Mode: {mode.upper()}")
    print("=" * 60)

    # 1. Clean previous build directories
    build_dir = PROJECT_ROOT / "build_backend"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    launcher_path = BACKEND_DIR / "app" / "launcher.py"
    if not launcher_path.exists():
        print(f"[ERROR] Launcher not found at {launcher_path}", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        "filenest-backend",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(build_dir),
        "--add-data",
        f"{BACKEND_DIR};backend",
        # Hidden imports for Uvicorn and FastAPI
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespans",
        "--hidden-import", "uvicorn.lifespans.on",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_settings",
        "--hidden-import", "watchdog",
        "--hidden-import", "fitz",
        "--hidden-import", "pypdfium2",
        "--hidden-import", "PIL",
        "--hidden-import", "docx",
        "--hidden-import", "openpyxl",
        "--hidden-import", "winocr",
        "--collect-submodules", "winrt",
        "--collect-submodules", "backend",
    ]

    # Mode A: Full Offline Bundle with PaddleOCR models
    temp_models_dir = PROJECT_ROOT / "temp_paddlex_models"
    if temp_models_dir.exists():
        shutil.rmtree(temp_models_dir, ignore_errors=True)

    if mode == "full":
        cmd.extend([
            "--collect-data", "paddleocr",
            "--collect-data", "paddlex",
        ])
        # Look for local cached models in ~/.paddlex
        user_paddlex = Path.home() / ".paddlex" / "official_models"
        if user_paddlex.exists():
            print(f"[*] Staging offline OCR models from {user_paddlex} ...")
            target_staging = temp_models_dir / "official_models"
            target_staging.mkdir(parents=True, exist_ok=True)
            for item in user_paddlex.iterdir():
                dest = target_staging / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            cmd.extend([
                "--add-data",
                f"{temp_models_dir};paddlex_models",
            ])
            print("[+] Added offline OCR models to build manifest.")
        else:
            print("[WARN] Local .paddlex models directory not found; building without bundled weights.")
    else:
        for mod in (
            "paddle",
            "paddleocr",
            "paddlex",
            "cv2",
            "pandas",
            "matplotlib",
            "scipy",
            "torch",
            "pytest",
            "IPython",
        ):
            cmd.extend(["--exclude-module", mod])

    cmd.append(str(launcher_path))

    print(f"[*] Running PyInstaller command: {' '.join(cmd[:8])} ...")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))

    # Clean temporary models staging
    if temp_models_dir.exists():
        shutil.rmtree(temp_models_dir, ignore_errors=True)

    # Copy output to src-tauri/resources/backend
    target_backend_dir = SRC_TAURI_RESOURCES
    if target_backend_dir.exists():
        shutil.rmtree(target_backend_dir, ignore_errors=True)
    target_backend_dir.parent.mkdir(parents=True, exist_ok=True)

    output_backend = DIST_DIR / "filenest-backend"
    print(f"[*] Copying bundled backend to {target_backend_dir} ...")
    shutil.copytree(output_backend, target_backend_dir)
    print(f"[SUCCESS] Backend packaged for Tauri resources at: {target_backend_dir}")

def main():
    parser = argparse.ArgumentParser(description="Build FileNest Backend Standalone Bundle")
    parser.add_argument(
        "--mode",
        choices=["full", "lite"],
        default="full",
        help="Build mode: 'full' (offline models included) or 'lite' (models downloaded on-demand)",
    )
    args = parser.parse_args()
    run_pyinstaller(args.mode)

if __name__ == "__main__":
    main()
