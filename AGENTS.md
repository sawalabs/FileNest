# Agent Entry Point — Desktop & Storage Manager

## 1. Before Doing Any Work

Before implementing any task:

1. Read this file.
2. Read `design/AGENT_INSTRUCTIONS.md`.
3. Read the target feature's `design/<feature>/README.md`.
4. Inspect all reference images inside the target feature's design folder.
5. Read applicable rules from `.agents/rules/`.
6. Read applicable skills from `.agents/skills/<skill-name>/SKILL.md`.
7. Inspect the existing project structure and code before making changes.

Do not start implementation before understanding the existing architecture and applicable design specifications.

## 2. Technology Stack

Use the following technology stack as the project standard.

### Desktop Application

- Framework: Tauri 2
- Frontend: React
- Language: TypeScript
- Build Tool: Vite
- Package Manager: pnpm
- Styling: Tailwind CSS
- UI Components: shadcn/ui
- Icons: Lucide React (`lucide-react`)

### Frontend Dependencies

Use these libraries as the default dependency choices.

| Dependency | Purpose |
|---|---|
| `react` | Frontend UI |
| `react-dom` | React rendering |
| `typescript` | Static typing |
| `vite` | Development server and build tool |
| `@vitejs/plugin-react` | React integration for Vite |
| `@tauri-apps/api` | Tauri frontend API |
| `@tauri-apps/plugin-dialog` | Native file and folder dialogs |
| `tailwindcss` | Utility-first styling |
| `lucide-react` | Application icons |
| `class-variance-authority` | Component variants |
| `clsx` | Conditional CSS classes |
| `tailwind-merge` | Merge Tailwind classes safely |
| `recharts` | Charts and data visualization |
| `@tanstack/react-table` | Advanced data tables |

Use shadcn/ui components built on Radix UI where appropriate.

Additional libraries may be introduced only when they provide a clear benefit and fit the existing architecture.

Do not install duplicate libraries that solve the same problem.

### Backend

- Language: Python
- API Framework: FastAPI
- Database: SQLite
- ORM: SQLAlchemy
- Database Migrations: Alembic
- Data Validation: Pydantic
- File Monitoring: Watchdog
- Background Processing: Python background worker and persistent SQLite job state

### Backend Dependencies

Use these libraries as the default dependency choices.

| Dependency | Purpose |
|---|---|
| `fastapi` | Backend REST API |
| `uvicorn` | ASGI server |
| `sqlalchemy` | ORM and database access |
| `alembic` | Database migrations |
| `pydantic` | Data validation and schemas |
| `pydantic-settings` | Application configuration |
| `watchdog` | Filesystem monitoring |
| `python-multipart` | Multipart file handling when required |
| `httpx` | HTTP client for external services |
| `PyMuPDF` | PDF metadata and content extraction |
| `python-docx` | DOCX document processing |
| `openpyxl` | Excel file processing |
| `Pillow` | Image metadata and processing |

Use Python standard library modules whenever they are sufficient, especially for:
- File operations
- Hashing
- Path validation
- JSON processing
- Logging
- Background task coordination

Do not install additional packages for functionality already available in the standard library.

### AI Integration

- AI Orchestrator: Hermes
- Model Gateway: 9Router
- Tool Integration: MCP
- Model communication: OpenAI-compatible API only when supported by the configured Hermes and 9Router versions.

Responsibilities:

- Hermes coordinates AI tasks.
- 9Router provides model access.
- MCP exposes restricted application tools.
- Python backend validates AI output.
- AI must never execute filesystem mutations directly.

Do not assume API endpoints, request formats, authentication methods, or configuration options without checking the actual installed versions and documentation.

### Windows Integration

Use Tauri 2 capabilities and plugins where appropriate.

Possible integrations:
- Native folder picker
- Native file dialogs
- System tray
- Desktop notifications
- Application startup
- Windows-specific file integration

Use only the required Tauri plugins. Configure permissions and capabilities explicitly.

The Python backend remains responsible for filesystem operations and transaction safety.

## 3. Icon System

Use **Lucide React (`lucide-react`)** as the only icon library.

Rules:

- Import icons directly from `lucide-react`.
- Use consistent icon sizes.
- Use icons that clearly represent their actions.
- Prefer simple and recognizable icons.
- Use the same icon for the same action throughout the application.
- Do not use emoji as application interface icons.
- Do not mix icon libraries.
- Do not create custom SVG icons when an appropriate Lucide icon already exists.

Examples:

| Usage | Lucide Icon |
|---|---|
| Overview | `LayoutDashboard` |
| Files | `Folder` |
| Storage | `HardDrive` |
| Organization | `FolderTree` |
| Smart Rename | `FilePenLine` |
| Monitoring | `Activity` |
| History | `History` |
| Settings | `Settings` |
| Search | `Search` |
| Refresh | `RefreshCw` |
| Add Folder | `FolderPlus` |
| Rename | `Pencil` |
| Delete | `Trash2` |
| Move | `FolderInput` |
| Copy | `Copy` |
| Download | `Download` |
| Upload | `Upload` |
| More Actions | `MoreHorizontal` |
| Success | `CheckCircle2` |
| Warning | `AlertTriangle` |
| Error | `CircleX` |
| Information | `Info` |
| AI Analysis | `Sparkles` |
| Expand | `ChevronDown` |
| Collapse | `ChevronRight` |

Example:

```tsx
import {
  Folder,
  HardDrive,
  Settings,
  RefreshCw,
} from "lucide-react";

<Folder size={18} />
<HardDrive size={18} />
<Settings size={18} />
<RefreshCw size={18} />
```

Do not use icons as decoration without a clear purpose.

## 4. Project Constraints

- Build a Windows desktop application using Tauri 2, React, TypeScript, Vite, Tailwind CSS, and shadcn/ui.
- Use the defined dependencies and icon system.
- Backend uses Python, FastAPI, SQLite, SQLAlchemy, and Alembic.
- AI integration uses Hermes and 9Router, with restricted MCP tools where appropriate.
- Only manually registered Managed Folders may be scanned or modified.
- AI may recommend and create structured plans; it must not execute filesystem changes directly.
- All filesystem mutations must pass through the backend Transaction Manager.
- Manual changes require approval.
- Previously approved rules may run automatically only within their exact approved scope.
- Never permanently delete files automatically.
- Never silently overwrite files.
- Do not invent files, APIs, schemas, dependencies, or completed work.
- Ask for clarification when an ambiguity materially affects architecture, data safety, or expected behavior.
- Keep changes scoped to the requested task.
- Reuse existing components, hooks, services, and utilities.
- Follow the existing architecture and naming conventions.

## 5. Dependency Management Rules

- Use pnpm for frontend dependency management.
- Use the existing Python dependency management approach in the repository.
- Never mix package managers.
- Do not manually edit generated lockfile contents.
- Do not install dependencies without a clear technical requirement.
- Before adding a dependency, check whether the functionality already exists in the project.
- Prefer maintained and widely adopted libraries.
- Avoid unnecessary dependencies and overlapping functionality.
- Keep dependency versions compatible with the existing project.
- Do not arbitrarily upgrade existing dependencies.
- Update the appropriate manifest and lockfile when dependencies change.
- Document why a new dependency is needed.

Do not assume a version number from this document. Follow the existing lockfiles and verify compatibility with the installed environment.

## 6. Design and UI Rules

- Follow `design/AGENT_INSTRUCTIONS.md`.
- Follow the target feature README.
- Use the provided design reference images.
- Keep visual consistency across all application pages.
- Use reusable components.
- Use consistent spacing, typography, colors, borders, and radii.
- Use Lucide React for all interface icons.
- Do not introduce unrelated visual styles.
- Avoid unnecessary gradients, decorative AI elements, and chatbot-first layouts.
- All visible controls must have working behavior.
- Provide loading, empty, error, and success states where appropriate.
- Support appropriate window resizing and scrolling.

If a design reference conflicts with safety requirements, safety requirements take precedence.

## 7. Architecture and Filesystem Safety

- Keep frontend and backend responsibilities separated.
- Frontend must not perform unrestricted filesystem operations.
- Backend owns filesystem access and validation.
- Only registered Managed Folders are allowed.
- Validate canonical paths before every filesystem operation.
- Do not follow symbolic links, junctions, or reparse points by default.
- Protect Windows system directories.
- Revalidate file state immediately before mutation.
- Detect destination collisions.
- Never silently overwrite.
- Never permanently delete files automatically.
- Use a Transaction Manager for every filesystem mutation.
- Record operations and execution results in History.
- Implement best-effort rollback for failed transactions.

## 8. AI and MCP Rules

- Hermes is the AI orchestrator.
- 9Router is the model gateway.
- MCP tools must be restricted and schema-validated.
- AI may analyze, classify, recommend, and generate structured plans.
- AI must not receive unrestricted shell or filesystem access.
- AI output must be validated by the backend.
- Never execute raw AI-generated commands.
- Never trust AI-generated paths without backend validation.
- All filesystem changes must pass through the Transaction Manager.
- Remote model access must respect user privacy and content-sharing settings.

## 9. Database and API Rules

- Use SQLite as the local database.
- Use SQLAlchemy for database access.
- Use Alembic for schema migrations.
- Use Pydantic for API validation.
- Keep database models, API schemas, and business logic separated.
- Do not modify the database schema without a migration.
- Use transactions for related database operations.
- Persist background job states.
- Handle errors explicitly.
- Do not expose sensitive filesystem information unnecessarily.

## 10. Testing and Quality

- Run relevant frontend checks.
- Run relevant backend checks.
- Run tests for modified functionality.
- Validate API request and response schemas.
- Test filesystem safety constraints.
- Test error handling and partial failures.
- Test Windows-specific functionality where applicable.
- Do not claim tests passed unless they were actually executed.
- Do not suppress errors to make checks appear successful.

## 11. Git Rules

After completing a requested implementation:

- Inspect `git status` before committing.
- Review the diff.
- Commit only changes related to the requested task.
- Never commit secrets, credentials, generated data, or unrelated changes.
- Do not overwrite or discard the user's existing changes.
- Create a Git commit if the repository is a Git repository and the user has not instructed otherwise.
- Report the commit hash.

Use a descriptive commit message.

## 12. Task Completion

After completing the task, report:

1. Summary of implementation.
2. Files created or changed.
3. Dependencies added or changed, including reasons.
4. Tests and checks actually run.
5. Known limitations or unresolved decisions.
6. Commit hash, if a commit was created.

Do not claim unfinished functionality as completed.