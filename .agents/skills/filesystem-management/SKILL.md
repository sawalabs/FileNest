---
name: filesystem-management
description: Implement safe scanning, indexing, searching, metadata extraction, and monitoring for manually registered folders.
---

# Filesystem Management

Use for Managed Folders, scanning, file indexing, search, metadata, hashing, and monitoring.

## Workflow

1. Identify the Managed Folder and its configured permissions.
2. Validate and canonicalize the root path.
3. Ensure every discovered or requested path remains inside the approved root.
4. Define scan scope and exclusions.
5. Implement scanning with bounded resource usage and progress reporting.
6. Persist metadata and scan state.
7. Handle inaccessible files, locked files, long paths, and concurrent changes.
8. Test with temporary directories and representative filesystem edge cases.

## Safety requirements

- Never scan arbitrary paths supplied by AI.
- Never escape the registered root.
- Do not follow symlinks, junctions, or reparse points by default.
- Do not read full file contents when metadata is sufficient.
- Hash files only when needed; support cancellation and progress.
- Treat watcher events as hints and re-stat the file before processing.
- Debounce and deduplicate watcher events.
- Do not mutate files in a scanner or watcher.
- Respect excluded paths and per-folder settings.

## Output

Report supported file types, exclusions, scan behavior, monitoring behavior, and known limitations.
