# Rule: Filesystem Safety

Apply to every scan, monitor, search, rename, move, create, or delete-related task.

## Scope

- Access only paths inside manually registered Managed Folders.
- Canonicalize and validate paths before every operation.
- Prevent path traversal and reject paths that escape an approved root.
- Do not follow symbolic links, junctions, or reparse points by default.
- Protect Windows system and application directories.
- Revalidate the source, destination, permissions, and file state immediately before mutation.

## Mutations

- AI must never mutate the filesystem directly.
- Every mutation must be represented by a validated change plan and executed by the backend Transaction Manager.
- Manual plans require explicit user approval.
- Automatic execution is allowed only for a previously approved, enabled rule and only for operations inside that rule's exact scope.
- Never silently overwrite an existing file.
- Never permanently delete files automatically.
- For cross-volume moves, use copy, verify, then delete only when the approved operation explicitly permits it.
- Handle partial failures and record each completed operation.

## Monitoring

- Debounce and deduplicate filesystem events.
- Treat watcher events as hints; re-check actual filesystem state before acting.
- Ignore events outside Managed Folders.
- Do not trigger unrestricted AI analysis for every event.
