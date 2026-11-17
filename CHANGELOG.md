# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-17

### Added
- **Cross-Module Folder Exclusions (FNE-84 – FNE-92)**:
  - Global and folder-level exclusion rules for directory paths and filename patterns.
  - Consistent exclusion enforcement across Files Manager, Storage Analyzer, Smart Organization, Smart Rename, and Watchdog Real-Time Monitoring.
- **Asynchronous Background Jobs Engine & UI (FNE-71 – FNE-83)**:
  - Persistent background job execution engine with floating progress tracker.
  - Immediate `trackJob` registration, session-aware state transition detection, and deep-link click-to-navigate with result hydration.
- **Review Plans & Smart Rename Safeguards (FNE-59 – FNE-62)**:
  - Isolated draft plans from immediate file preview, enabling inspection and editing in the Review Plans tab prior to execution.
  - Added protected folder safeguards to Smart Rename.
- **Drive Roots & Managed Folders (FNE-4 – FNE-13)**:
  - Full drive root registration support (e.g., `C:\`, `D:\`) with automatic detection.
  - Automatic subsumption of child folders upon drive root registration.
  - Enhanced Windows system path protection and reactivation of disabled folder records.
- **Cross-Drive File Operations (FNE-14)**:
  - Robust cross-drive and cross-volume file moves via staged copy, verification, and conflict detection.
- **Documentation Suite & Visual UI Previews**:
  - Comprehensive documentation portal in `docs/` (`USER_GUIDE.md`, `UI_PREVIEWS.md`, `ARCHITECTURE.md`, `FILESYSTEM_SAFETY_VERIFICATION.md`, `PACKAGING_AND_BUILD.md`, `WINDOWS_DEPLOYMENT.md`).
  - Added visual UI preview screenshots and updated README previews.
- **QA & Testing Infrastructure**:
  - Integrated autonomous desktop QA skill (`tauri-ai-qa`) for automated Windows UI and regression testing.

### Fixed
- Resolved quick action filename validation and path collision handling (BUG-001 through BUG-011).
- Added fallback to OCR keyword extraction during offline AI simulation in Smart Rename.
- Fixed drive re-registration allowing re-enabling previously unregistered managed folders.
- Fixed floating task notification click-to-navigate and result hydration on completed jobs.

---

## [0.1.0] - 2026-11-14

### Added
- **Initial Production Release (Windows x64)**:
  - **3-Pane Files Manager** with bounded preview streaming and on-demand OCR.
  - **Storage Analyzer & Duplicate Finder** with review-backed cleanup plans.
  - **Smart Organization** with automatic Protected Project & SDK/DLL Bundle detection.
  - **Smart Rename** powered by hybrid Windows Native OCR + PaddleOCR fallback.
  - **Review Changes & Transaction Manager** with TOCTOU validation, quarantine staging, and rollback.
  - **Real-Time Watchdog Monitoring** and scoped approved automation rules.
  - **Contextual AI Assistant** via 9Router gateway and OpenRouter auto-fallback.
  - **Hardened Security**: Windows Credential Manager (DPAPI), automatic audit redaction, ephemeral `X-App-Token` session auth, strict CSP, and Managed Folder confinement.
  - **Standalone Windows Installers**: NSIS Setup (`.exe`) and MSI Enterprise Package (`.msi`).
