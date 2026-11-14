---
name: react-typescript
description: Build maintainable React and TypeScript features, components, hooks, and frontend service integrations.
---

# React + TypeScript

Use for React components, pages, hooks, state, routing, and frontend integration.

## Workflow

1. Inspect package scripts, tsconfig, routing, existing component patterns, and state management.
2. Reuse existing dependencies and conventions.
3. Define typed props and API models.
4. Separate view components from data-fetching and domain logic.
5. Implement state transitions and user interactions.
6. Handle loading, empty, error, and success states.
7. Run type checking, linting, and relevant tests.

## Standards

- Avoid `any`; use explicit types or `unknown` with safe narrowing.
- Keep components focused and reasonably small.
- Use custom hooks for reusable stateful logic.
- Avoid duplicating API calls and business rules in components.
- Keep API access in the existing service layer.
- Avoid effects for values that can be derived during render.
- Clean up subscriptions and event listeners.
- Use stable keys for lists.
- Ensure forms have validation and clear error feedback.
- Do not couple UI components directly to SQLite or filesystem implementation.

## Output

Report changed components, service contracts, state behavior, and checks performed.
