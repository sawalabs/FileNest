# Rule: Testing, Validation, and Git

Apply to all implementation tasks.

- Run the narrowest relevant tests first, then broader checks when practical.
- Run frontend type checking and linting when available.
- Run backend tests and static checks when available.
- Test filesystem safety using temporary test directories, never real user folders.
- Test approval and approved-rule paths separately.
- Test failure, conflict, and retry behavior for file operations.
- Do not claim tests passed unless they were executed successfully.
- Inspect `git status` and the diff before committing.
- Do not include secrets, local databases, user files, build artifacts, or unrelated modifications in a commit.
- Commit completed work when the repository is under Git and the user has not instructed otherwise.
- Use a concise commit message describing the change.
- Report the commit hash and any checks not run.
