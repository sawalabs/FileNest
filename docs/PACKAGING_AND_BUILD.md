# FileNest Desktop & Storage Manager — Packaging & Build Guide

## 1. Architecture Overview

FileNest is a high-performance Windows desktop application built with a separated client-service architecture:

```
+--------------------------------------------------------------+
|             FileNest Desktop Shell (Tauri 2)                 |
|  +--------------------------------------------------------+  |
|  |     Frontend UI: React 18 + TypeScript + Vite          |  |
|  |     Styling: Tailwind CSS + shadcn/ui                  |  |
|  |     Icons: Lucide React (Only approved library)        |  |
|  +--------------------------------------------------------+  |
|                            | Local HTTP / IPC                |
|  +--------------------------------------------------------+  |
|  |     Backend Service: FastAPI (Python 3.11)             |  |
|  |     Database: SQLite 3 in WAL mode (SQLAlchemy ORM)    |  |
|  |     Monitoring: Watchdog Observer (Background Thread)  |  |
|  |     Secrets: Windows Credential Manager (keyring)      |  |
|  |     Safety: PathValidator + Transaction Manager        |  |
|  +--------------------------------------------------------+  |
+--------------------------------------------------------------+
```

---

## 2. Prerequisites for Windows

To build and run FileNest on Windows 10/11 x64, ensure the following tools are installed:

| Component | Minimum Version | Purpose |
|---|---|---|
| **Node.js** | `>= 18.0` | Frontend tooling & execution |
| **pnpm** | `>= 9.0` | Fast, deterministic package manager |
| **Python** | `3.11.x` | Backend runtime & scientific extraction |
| **Rust & Cargo** | `>= 1.77` | Compiling the Tauri 2 native desktop shell |
| **Visual Studio Build Tools** | `2022` | MSVC C++ compiler & Windows SDK |
| **WebView2** | Evergreen Runtime | Built-in on modern Windows 10 & 11 |

---

## 3. Local Development Setup

### Step 1: Install Frontend Dependencies
```powershell
pnpm install
```

### Step 2: Initialize Python Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Step 3: Run the Application
You can use the automated startup supervisor:
```powershell
.\scripts\start-filenest.ps1
```
Or launch services individually in separate terminals:
- **Terminal 1 (Backend):**
  ```powershell
  .venv\Scripts\python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
  ```
- **Terminal 2 (Tauri Desktop):**
  ```powershell
  pnpm run desktop
  ```

---

## 4. Production Build & Packaging

### 4.1 Frontend Compilation
Run the TypeScript strict compiler and Vite production bundler:
```powershell
pnpm run build
```
- Transpiles all React/TypeScript components with strict type-checking.
- Emits optimized assets into `dist/`.

### 4.2 Desktop Packaging (Tauri 2)
To generate production binaries and Windows installers:
```powershell
pnpm run desktop:build
```
Or via Cargo directly:
```powershell
cargo tauri build
```

### Generated Artifacts
Tauri packages the application into the following outputs in `src-tauri/target/release/bundle/`:
1. **Standalone Portable Executable**: `src-tauri/target/release/filenest.exe`
2. **NSIS Windows Installer**: `src-tauri/target/release/bundle/nsis/FileNest_0.1.0_x64-setup.exe`
3. **MSI Enterprise Package**: `src-tauri/target/release/bundle/msi/FileNest_0.1.0_x64_en-US.msi`

---

## 5. Security & Permission Configuration

Tauri 2 isolates webview privileges using capability configurations in `src-tauri/capabilities/default.json`:
- `core:default`: Basic window and application lifecycle controls.
- `dialog:default`: Native Windows folder and file pickers via `@tauri-apps/plugin-dialog`.
- **Zero Raw Filesystem Permissions**: The web frontend is granted **no direct filesystem access**. All file operations must route through the local FastAPI Transaction Manager.

---

## 6. Known Limitations & Recommendations

1. **Windows Path Length Limits (MAX_PATH)**:
   - Deep nested directories beyond 260 characters require Windows long path support enabled (`LongPathsEnabled = 1` in `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem`) or UNC path prefixes.
2. **Windows System Directories**:
   - System folders (`C:\Windows`, `C:\Program Files`, `System32`, drive root `C:\`) cannot be registered as Managed Folders by design to prevent OS instability.
3. **Burst Write Operations**:
   - Filesystem watchers use a sliding debounce interval (default 1000ms) to suppress redundant notifications caused by Windows applications saving temp files.
4. **Credential Isolation**:
   - Secrets (API keys, Hermes tokens) are persisted in Windows Credential Manager and will not migrate via ordinary database backups. Re-enter credentials when moving the database across workstations.
