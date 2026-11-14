# Rule: Database and API Contracts

Apply to SQLite, SQLAlchemy, Alembic, and frontend/backend integration.

- Inspect existing models, migrations, and API contracts before changing them.
- Keep database access in repositories or the established data-access layer.
- Use migrations for schema changes.
- Define explicit request and response schemas.
- Keep frontend TypeScript types aligned with backend contracts.
- Do not fabricate endpoint paths, fields, enum values, or response examples.
- Use pagination for potentially large lists.
- Use stable identifiers rather than relying on display names or filesystem paths as database primary keys.
- Persist task status, rule execution records, approvals, and audit events where required.
- Do not store secrets or unnecessary raw document contents in the database.
- Consider transaction boundaries and concurrency when updating task and file-operation state.
