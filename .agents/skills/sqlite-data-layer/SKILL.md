---
name: sqlite-data-layer
description: Design and implement SQLite persistence with SQLAlchemy and Alembic for local desktop applications.
---

# SQLite Data Layer

Use for database models, repositories, migrations, and persistence behavior.

## Workflow

1. Inspect existing database configuration and models.
2. Identify entities, relationships, uniqueness, and lifecycle.
3. Define SQLAlchemy models and constraints.
4. Create an Alembic migration.
5. Implement repository methods.
6. Add tests for constraints, transactions, and persistence.
7. Verify upgrade behavior against an existing development database.

## Standards

- Use stable IDs and explicit foreign keys.
- Add indexes for frequently queried fields.
- Use constraints to protect data integrity.
- Store timestamps consistently.
- Use transactions for related updates.
- Persist task states, approvals, rule executions, and audit logs.
- Avoid storing raw file contents unless explicitly required.
- Never store API keys or tokens in plaintext.
- Do not edit production database files manually.
- Do not rewrite migration history that may already have been applied.

## Output

Report schema changes, migration name, relationships, indexes, and tests performed.
