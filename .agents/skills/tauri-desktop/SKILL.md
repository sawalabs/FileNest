---
name: tauri-desktop
description: Implement Windows desktop integration using Tauri 2, including app lifecycle, tray, startup, and secure frontend-backend communication.
---

# Tauri Desktop

Use for Tauri configuration, Rust commands, app lifecycle, tray, autostart, packaging, and desktop integration.

## Workflow

1. Inspect the installed Tauri version and existing plugins/configuration.
2. Read current Tauri project conventions and capabilities.
3. Identify whether the task belongs in the web frontend, Tauri/Rust layer, or Python backend.
4. Apply the narrowest implementation.
5. Review permissions and capabilities.
6. Test the behavior on the supported Windows environment.

## Standards

- Use Tauri 2 APIs and plugin versions compatible with the project.
- Apply least-privilege capabilities.
- Do not expose arbitrary command execution to the frontend.
- Validate arguments crossing the frontend/Rust boundary.
- Keep long-running domain work in the Python backend where specified.
- Manage Python sidecar startup, health checks, shutdown, and restart behavior explicitly.
- Use loopback communication with an authentication token where required.
- Keep secrets out of frontend bundles, logs, and plain configuration files.
- Ensure closing the main window and exiting the application have clearly defined, separate behavior.
- Do not assume a plugin exists; inspect dependencies first.

## Output

Report changed Tauri configuration, capabilities, plugins, lifecycle behavior, and Windows tests performed.
