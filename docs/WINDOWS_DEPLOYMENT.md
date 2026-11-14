# Windows Production Deployment & Operational Readiness Guide

## 1. Scope & Purpose

This guide outlines the production deployment, packaging, operational monitoring, and disaster recovery procedures for **FileNest (Desktop & Storage Manager)** on Windows 10/11 64-bit systems. 

FileNest operates as a local Windows desktop application utilizing Tauri 2 (Rust) for the desktop window and UI shell, and a local Python FastAPI ASGI daemon for transaction safety, indexing, and background monitoring. **No Docker daemon or container runtime is required or used.**

---

## 2. System Requirements & Prerequisites

### 2.1 Target Operating System
- **Supported OS:** Windows 10 64-bit (Version 1903 or higher, Build 18362+) / Windows 11 64-bit (all builds).
- **Architecture:** x86_64 / x64.
- **Filesystem:** NTFS or ReFS with Long Path support recommended (`LongPathsEnabled = 1`).

### 2.2 System Runtime Prerequisites
1. **Microsoft Edge WebView2 Evergreen Runtime**:
   - Pre-installed on Windows 11 and modern Windows 10 updates.
   - If missing on older Windows 10 enterprise builds, install the [WebView2 Evergreen Bootstrapper](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).
2. **Python 3.11 (64-bit)**:
   - Python 3.11.x installed to user or system directory (`python --version` >= 3.11).
3. **Microsoft Visual C++ Redistributable 2015–2022 (x64)**:
   - Required for Python native extensions (e.g. `Pillow`, `PyMuPDF`).
4. **Windows Credential Manager**:
   - Built-in Windows DPAPI service (`vaultcli.dll` / `advapi32.dll`) used automatically by FileNest for encrypted zero-leak secret persistence.

---

## 3. Production Packaging (Zero-Docker Workflow)

The application packages entirely natively on Windows without container virtualization:

### 3.1 Frontend Build
Compiles all TypeScript and React assets into minified production static bundles:
```powershell
pnpm run build
```
Output directory: `dist/` containing `index.html`, minified JS chunks, and CSS.

### 3.2 Native Tauri Desktop Shell
Compiles the Rust window shell and packages the installer:
```powershell
pnpm run desktop:build
```
Produces:
- `src-tauri/target/release/filenest.exe` (Standalone executable)
- `src-tauri/target/release/bundle/nsis/FileNest_0.1.0_x64-setup.exe` (Self-contained NSIS Installer)
- `src-tauri/target/release/bundle/msi/FileNest_0.1.0_x64_en-US.msi` (MSI enterprise installer)

### 3.3 Backend Virtual Environment Assembly
For distribution alongside the desktop binary:
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt --no-warn-script-location
```

---

## 4. Configuration & Credential Hardening

FileNest enforces zero credential exposure in source code, configuration files, SQLite tables, or log files:

### 4.1 Environment Configuration (`.env`)
Production settings reside in `.env` located in the application root directory:
```env
PROJECT_NAME="Desktop & Storage Manager"
VERSION="0.1.0"
ENVIRONMENT="production"
DEBUG=false
LOG_LEVEL="INFO"
API_V1_PREFIX="/api/v1"
DATABASE_URL="sqlite:///./data/filenest.db"
CORS_ORIGINS=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "https://tauri.localhost"]
WATCHDOG_DEBOUNCE_SECONDS=1.0
SCAN_BATCH_SIZE=100
MAX_PREVIEW_SIZE_BYTES=10485760
```

### 4.2 Credential Storage via Windows Credential Manager
Secrets such as the 9Router API Key, Hermes tokens, or integration credentials are **never written to `.env` or the SQLite database**. They are securely stored in Windows Credential Manager under the target name `FileNestDesktop`:
- User credentials persist in Windows Credential Vault encrypted via DPAPI.
- Can be viewed or managed natively in `Control Panel -> Credential Manager -> Windows Credentials`.

---

## 5. Database Management, Migrations & Recovery

### 5.1 SQLite Configuration
- Location: `./data/filenest.db`
- Journal Mode: **WAL (Write-Ahead Logging)** enabled automatically by SQLAlchemy connect listener for high-concurrency non-blocking reads.
- Synchronous Mode: `NORMAL`.
- Foreign Keys: `PRAGMA foreign_keys=ON` strictly enforced.

### 5.2 Database Migrations (Alembic)
Check current migration status:
```powershell
.\.venv\Scripts\python -m alembic current
```
Upgrade database to the latest schema:
```powershell
.\.venv\Scripts\python -m alembic upgrade head
```
Roll back to base or previous revision:
```powershell
.\.venv\Scripts\python -m alembic downgrade -1
```

### 5.3 Backup & Disaster Recovery
To perform an online, non-blocking backup of the production database:
```powershell
# Backup script using SQLite safe online backup API or copy
.\.venv\Scripts\python -c "
import sqlite3, shutil, datetime
now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
src = sqlite3.connect('data/filenest.db')
dst = sqlite3.connect(f'data/filenest_backup_{now}.db')
with dst:
    src.backup(dst)
dst.close()
src.close()
print(f'Backup created: filenest_backup_{now}.db')
"
```

---

## 6. Runtime Observability & Health Telemetry

FileNest exposes a health and subsystem diagnostic probe endpoint:

### Endpoint: `GET /api/v1/health`
Response payload sample:
```json
{
  "status": "ok",
  "project": "Desktop & Storage Manager",
  "version": "0.1.0",
  "environment": "production",
  "timestamp": "2026-11-02T15:50:00Z",
  "subsystems": {
    "database": {
      "status": "ok",
      "message": "SQLite database connected and responding",
      "latency_ms": 1.25,
      "details": {
        "engine": "sqlite",
        "database_url": "sqlite:///./data/filenest.db"
      }
    },
    "security": {
      "status": "ok",
      "message": "Windows Credential Manager active",
      "latency_ms": null,
      "details": {
        "vault_service": "FileNestDesktop",
        "os_keyring_available": true
      }
    },
    "ai_gateway": {
      "status": "ok",
      "message": "9Router endpoint configured: http://localhost:8080/v1",
      "latency_ms": null,
      "details": {
        "provider": "9router",
        "default_model": "deepseek-coder",
        "has_api_key": true
      }
    },
    "monitoring": {
      "status": "ok",
      "message": "Monitoring service active with 2 watcher(s)",
      "latency_ms": null,
      "details": {
        "active_watchers": 2
      }
    }
  }
}
```

### Subsystem Health States:
- `database`: Evaluates SQLite read/write responsiveness and latency. Returns `error` and degrades overall status if the file is locked or corrupt.
- `security`: Verifies Windows DPAPI Keyring availability. Returns `warning` if falling back to memory vault.
- `ai_gateway`: Verifies 9Router gateway endpoint configuration and API key status.
- `monitoring`: Inspects background Watchdog observers for all registered Managed Folders.

---

## 7. Production Process Supervision

The application includes an automated PowerShell startup supervisor: `scripts\start-filenest.ps1`.
- Supervises background ASGI worker (`uvicorn backend.app.main:app`).
- Waits for health endpoint check on `http://127.0.0.1:8000/api/v1/health` to succeed before launching Tauri desktop.
- Traps exit signals (`CTRL+C` or window close) to gracefully terminate child worker threads and release filesystem locks.
