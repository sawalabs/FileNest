---
name: python-fastapi
description: Implement Python backend APIs, services, workers, validation, and background tasks using FastAPI.
---

# Python + FastAPI

Use for backend API endpoints, services, workers, and domain logic.

## Workflow

1. Inspect Python version, dependencies, app startup, and existing architecture.
2. Locate the correct router, schema, service, and repository.
3. Define or reuse typed request and response schemas.
4. Implement business logic in services, not route handlers.
5. Add validation, logging, and explicit error handling.
6. Add tests for success and failure paths.
7. Run relevant tests and type/static checks.

## Standards

- Use type hints.
- Keep API routers thin.
- Avoid global mutable state.
- Use dependency injection where the project already follows it.
- Keep blocking filesystem or document processing from blocking the event loop.
- Persist long-running task state.
- Make task operations idempotent where practical.
- Do not expose unrestricted filesystem access through API parameters.
- Do not execute shell commands from model-generated strings.

## Output

Report endpoints, schemas, services, persistence changes, and tests performed.
