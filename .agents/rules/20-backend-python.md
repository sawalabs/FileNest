# Rule: Backend Python

Apply to Python and FastAPI tasks.

- Use FastAPI, SQLAlchemy, Alembic, and SQLite as established by the project.
- Separate API routers, schemas, services, repositories, and domain logic.
- Use type hints and request/response validation.
- Keep route handlers thin; place business logic in services.
- Handle errors explicitly and return safe, predictable API responses.
- Use structured logging; never log API keys, tokens, or document contents unnecessarily.
- Use asynchronous processing only where it provides a clear benefit.
- Long-running scans and AI tasks must use persistent task state and be resumable where practical.
- Do not run arbitrary shell commands based on model output.
- Do not expose unrestricted filesystem paths or operations through API endpoints.
- Add or update migrations when database schema changes. Do not silently modify an existing database schema.
