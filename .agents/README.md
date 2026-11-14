# .agents

This directory contains reusable agent skills and project rules.

## Structure

```text
.agents/
├── README.md
├── rules/
│   ├── 00-project-baseline.md
│   ├── 10-frontend-ui.md
│   ├── 20-backend-python.md
│   ├── 30-filesystem-safety.md
│   ├── 40-ai-hermes-9router-mcp.md
│   ├── 50-database-and-api.md
│   └── 60-testing-and-git.md
└── skills/
    ├── desktop-ui-implementation/SKILL.md
    ├── react-typescript/SKILL.md
    ├── tauri-desktop/SKILL.md
    ├── python-fastapi/SKILL.md
    ├── filesystem-management/SKILL.md
    ├── transaction-manager/SKILL.md
    ├── hermes-9router-mcp/SKILL.md
    └── sqlite-data-layer/SKILL.md
```

## How to use

- `AGENTS.md` at the repository root is the entry point.
- Rules define constraints that apply to relevant work.
- Skills provide task-specific workflows and implementation guidance.
- Feature-specific behavior and acceptance criteria remain in `design/<feature>/README.md`.
- Do not copy large feature specifications into skills. Link the work to the relevant feature README instead.

Read only the rules and skills relevant to the current task to reduce context usage.
