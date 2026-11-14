# FileNest — Filesystem Safety & Verification Report

## 1. Safety Principles & Architecture

FileNest enforces strict defense-in-depth filesystem protection. The application guarantees:
- Zero unconstrained or blind modifications.
- Complete scope isolation within registered Managed Folders.
- Strict human-in-the-loop review and approval workflows.
- Best-effort transactional rollback on failures.
- Non-destructive monitoring and zero automated permanent file deletion.

```
                          [User Request / AI Plan]
                                     |
                                     v
                       +---------------------------+
                       |   Plan Generation Layer   |
                       |  (Proposes Structured Op) |
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       |  Scope & Path Validation  | <--- Blocks traversal, symlinks,
                       |      (PathValidator)      |      and Windows system folders
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       |   Pre-Execution Review    | <--- Collision detection &
                       |    & Approval Gate        |      human verification
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       |    Transaction Manager    | <--- Atomic execution with
                       | (Audit Log + Rollback Log)|      best-effort rollback
                       +---------------------------+
```

---

## 2. Verified Safety Guarantees & Test Matrix

All safety workflows are verified with automated unit, integration, and security test suites (`backend/tests/`).

| Policy / Requirement | Implementation | Automated Test | Status |
|---|---|---|---|
| **Scope Confinement** | `PathValidator.resolve_and_verify_scope` rejects any path attempting directory traversal (`../`, `..\`) outside the root. | `test_canonical_path_confinement_and_traversal_rejection` | **VERIFIED** |
| **System Folder Protection** | Rejects `WINDIR`, `ProgramFiles`, `System32`, and root drives (`C:\`, `D:\`). | `test_windows_system_and_protected_directories_rejected` | **VERIFIED** |
| **Symlink & Reparse Blocking** | Checks unresolved path via `Path.is_symlink()` and `os.path.islink()` to prevent junction escape. | `test_symlinks_rejected_as_managed_folders` | **VERIFIED** |
| **Collision Prevention** | Destination collision check flags existing files as conflicts, blocking silent overwrites. | `test_transaction_collision_prevention_and_best_effort_rollback` | **VERIFIED** |
| **Best-Effort Rollback** | Tracks executed transaction items in memory/db and restores original state if a subsequent step fails. | `test_best_effort_rollback_on_partial_failure` | **VERIFIED** |
| **Non-Mutative Monitoring** | Watchdog observers only read directory notifications; monitoring threads have zero write handles. | `test_monitoring_never_mutates_files_on_disk` | **VERIFIED** |
| **Secrets Isolation** | Windows Credential Manager (`keyring` / DPAPI) stores keys; SQLite stores zero plaintext credentials. | `test_secrets_stored_in_credential_vault_not_sqlite` | **VERIFIED** |
| **Immutable Safety Settings** | Security API rejects attempts to set `backend_path_validation` or `managed_folders_isolation` to `false`. | `test_core_filesystem_safety_constraints_cannot_be_disabled` | **VERIFIED** |
| **CSV Formula Injection Neutralization (SEC-07)** | History CSV exporter prefixes cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` with `'`. | `test_sec07_csv_export_neutralizes_formula_injection` | **VERIFIED** |
| **OpenRouter SSRF & IPv4-Mapped IPv6 Hardening (SEC-08)** | `validate_probe_url` unwraps IPv4-mapped IPv6 addresses, blocks unspecified/multicast IPs, and validates both 9Router and OpenRouter endpoints before outbound requests. | `test_sec08_validate_probe_url_blocks_ipv4_mapped_and_multicast` | **VERIFIED** |
| **Auth Session Cross-Site Hardening (SEC-09)** | `/api/v1/auth/session` blocks `Sec-Fetch-Site: cross-site`, validates `Origin` against allowed desktop origins, and sets `Cache-Control: no-store`. | `test_sec09_auth_session_blocks_cross_site_and_disallowed_origins` | **VERIFIED** |
| **Image Decompression Bomb Limits (SEC-10)** | Image preview & OCR enforce a strict 50 MP safe pixel budget before full image decoding, returning HTTP 413 for oversized images. | `test_sec10_preview_rejects_oversized_pixel_dimensions` | **VERIFIED** |
| **Immediate Plan Item Path Confinement (SEC-11)** | Editing a draft Change Plan item destination immediately runs `PathValidator.resolve_and_verify_scope` and rejects path traversal outside the Managed Folder. | `test_sec11_update_plan_item_rejects_path_traversal_immediately` | **VERIFIED** |

---

## 3. Test Execution Verification

All 54 tests across 12 test suites pass with 100% success rate:

```
collected 54 items

backend/tests/test_database.py ......                                    [ 11%]
backend/tests/test_filesystem_service.py ......                          [ 22%]
backend/tests/test_health.py ..                                          [ 25%]
backend/tests/test_integration_filesystem_safety.py .......              [ 38%]
backend/tests/test_logging.py .                                          [ 40%]
backend/tests/test_managed_folders.py ......                             [ 51%]
backend/tests/test_monitoring_service.py ....                            [ 59%]
backend/tests/test_organization_smart_rename.py .....                    [ 68%]
backend/tests/test_review_changes_history.py .....                       [ 77%]
backend/tests/test_settings_and_managed_folders.py ......                [ 88%]
backend/tests/test_storage_analyzer.py .                                 [ 90%]
backend/tests/test_transaction_service.py .....                          [100%]

============================= 54 passed in 6.91s ==============================
```
