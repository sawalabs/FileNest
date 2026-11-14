---
name: transaction-manager
description: Design and implement validated file-operation plans, approvals, deterministic execution, audit logs, and best-effort rollback.
---

# Transaction Manager

Use for creating folders, moving files, renaming files, approved automation, execution, verification, and rollback.

## Workflow

1. Accept a structured change plan, never free-form shell instructions.
2. Validate schema and operation types.
3. Verify the operation is within a registered Managed Folder.
4. Check source existence and current file state.
5. Check destination validity and conflicts.
6. Determine whether manual approval or a matching approved rule authorizes execution.
7. Persist the plan and operation state.
8. Execute operations deterministically.
9. Verify results and record audit events.
10. Handle partial failure and offer best-effort rollback where safe.

## Required safeguards

- Revalidate immediately before each mutation.
- Detect stale plans using relevant metadata and hashes where appropriate.
- Never silently overwrite.
- Never permanently delete automatically.
- For cross-volume moves, copy and verify before deleting the source, and only if deletion is explicitly authorized.
- Make operations idempotent or detect already-completed work where practical.
- Record original path, destination, operation, timestamps, status, and recovery information.
- Stop or quarantine operations when an unexpected conflict occurs.
- Rollback must not overwrite newer user data.

## Approved rules

Automatic execution is allowed only when the rule:
- Is enabled and previously approved.
- Matches the exact Managed Folder and operation scope.
- Has not been changed since approval.
- Does not encounter an ambiguous or risky condition.

Anything outside those conditions must go to Review Changes.

## Output

Report validation rules, approval checks, execution guarantees, partial-failure handling, audit data, and rollback limitations.
