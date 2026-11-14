import os
import sys
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "production")

# When running frozen in PyInstaller, adjust sys.path and environment
if getattr(sys, "frozen", False):
    os.environ["ENVIRONMENT"] = "production"
    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

# Check for bundled offline paddle/paddlex models
def setup_bundled_models():
    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    bundled_paddlex = base_dir / "paddlex_models"
    if bundled_paddlex.exists():
        os.environ["PADDLEX_HOME"] = str(bundled_paddlex)
        print(f"[FileNest Backend] Using bundled offline OCR models at {bundled_paddlex}")

setup_bundled_models()

import uvicorn
from backend.app.core.config import settings
from backend.app.main import app

def main():
    import multiprocessing
    multiprocessing.freeze_support()

    port = int(os.environ.get("PORT", settings.PORT))
    host = os.environ.get("HOST", settings.HOST)

    print(f"[FileNest Backend] Starting server on {host}:{port} ...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )

if __name__ == "__main__":
    main()
