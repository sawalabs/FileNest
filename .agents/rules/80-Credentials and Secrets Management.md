
## 1. Core Rule

Never hardcode sensitive information anywhere in the source code, configuration files, scripts, tests, build files, or documentation.

Sensitive information includes:
- API keys and access tokens
- Passwords and database credentials
- Authentication secrets and signing keys
- Private keys and certificates
- Session tokens and refresh tokens
- Hermes and 9Router credentials
- Internal service credentials
- Any other value that grants access to a system or resource

Use secure runtime configuration and operating-system credential storage instead.

## 2. Prohibited Practices

Agents MUST NOT:

- Hardcode credentials in source code.
- Commit real credentials to Git.
- Put secrets in frontend code, React environment variables, or bundled assets.
- Store plaintext passwords, API keys, or tokens in SQLite.
- Include secrets in logs, error messages, analytics, or debug output.
- Put credentials directly in command-line arguments where they may be exposed in process listings.
- Include real credentials in screenshots, examples, test fixtures, or documentation.
- Use production credentials in automated tests.
- silently fall back to hardcoded credentials when configuration is missing.

Never use patterns such as:

```python
API_KEY = "real-api-key"
PASSWORD = "my-password"
```

```typescript
const API_TOKEN = "real-token";
```

## 3. Approved Storage

Use the following storage strategy:

| Data | Approved storage |
|---|---|
| API keys and access tokens | Windows Credential Manager |
| Service passwords | Windows Credential Manager |
| 9Router credentials | Windows Credential Manager |
| Hermes credentials | Windows Credential Manager, if required |
| Private keys | OS-protected secure storage or protected key files |
| Non-sensitive application settings | SQLite |
| Non-sensitive configuration | Configuration files or environment variables |

For this Windows desktop application, prefer Windows Credential Manager through the backend.

The frontend must never directly retrieve or manage secrets.

## 4. Environment Variables

Environment variables may be used for local development and temporary runtime configuration.

Rules:
- Provide `.env.example` containing placeholder values only.
- Add `.env`, `.env.*` containing real secrets, and credential files to `.gitignore`.
- Never commit real `.env` files.
- Validate required environment variables at application startup.
- Do not expose backend environment variables to the frontend.
- Do not use frontend variables such as `VITE_API_KEY` for secrets.
- Never assume environment variables are encrypted or secure storage.

Example:

```env
ROUTER_BASE_URL=http://127.0.0.1:20128/v1
ROUTER_API_KEY=replace-with-your-local-key
```

The example above is documentation only. Real values must not be committed.

## 5. Credential Access Architecture

All credential access must go through the Python backend.

Expected flow:

1. User enters or updates a credential through Settings.
2. Frontend sends the credential to a dedicated backend endpoint over the local application channel.
3. Backend validates the input.
4. Backend stores the credential in Windows Credential Manager.
5. Backend returns only success/failure and non-sensitive metadata.
6. When a service needs authentication, backend retrieves the credential at runtime.
7. Backend sends the credential only to the intended service.

Never return the actual secret to the frontend after saving it.

## 6. SQLite Restrictions

SQLite must not contain:
- API keys
- Passwords
- Access tokens
- Refresh tokens
- Private keys
- Credential-bearing connection strings

SQLite may store:
- Credential reference/key identifiers
- Provider names
- Service URLs
- Credential configuration status
- Last successful connection timestamp
- Non-sensitive authentication metadata

Do not store a secret merely because the database is local.

## 7. Logging and Error Handling

Secrets must be redacted from all application logs.

Examples of sensitive fields to redact:
- `password`
- `api_key`
- `token`
- `access_token`
- `refresh_token`
- `authorization`
- `client_secret`

Never log:
- Full HTTP Authorization headers
- Request bodies containing credentials
- Credential Manager values
- Full connection strings containing passwords

Use sanitized error messages. Do not include secret values in exceptions or tracebacks exposed to users.

## 8. Frontend Security

- Frontend code must never contain secrets.
- Do not persist secrets in localStorage, sessionStorage, IndexedDB, or browser-accessible state.
- Do not put credentials in URLs or query parameters.
- Clear password input fields after successful submission.
- Mask secret input fields.
- Never display previously saved secret values.
- Provide an explicit action to replace or remove stored credentials.

## 9. Git and Repository Protection

Before committing:
- Check staged files for credentials.
- Ensure `.gitignore` excludes local secret files.
- Ensure example configuration contains placeholders only.
- Never commit private keys or credential backups.

If a secret is accidentally committed:
1. Treat it as compromised.
2. Revoke or rotate the credential immediately.
3. Remove it from the repository.
4. Clean Git history when appropriate.
5. Do not assume deleting the latest commit or file invalidates the leaked credential.

## 10. Testing

- Use fake credentials in tests.
- Mock credential storage where appropriate.
- Never require production credentials to run unit tests.
- Add tests for missing credentials, invalid credentials, and credential storage failures.
- Verify logs do not expose submitted credentials.
- Verify the frontend never receives saved secret values.

## 11. AI Agent Restrictions

AI agents MUST:
- Never request real credentials in prompts or chat unless strictly necessary for a user-directed configuration step.
- Never copy secrets into generated code or documentation.
- Never expose secrets in task descriptions, Trello comments, commits, or reports.
- Use placeholders when demonstrating configuration.
- Avoid reading unrelated credential files.
- Never send credentials to an AI model or external service unless explicitly required for the intended authenticated service request and authorized by the user.

AI agents MUST NOT:
- Search the entire machine for credentials.
- Read Windows Credential Manager contents for unrelated tasks.
- Export, print, or summarize stored secrets.
- Modify or delete existing credentials without explicit user authorization.

## 12. Acceptance Criteria

- No hardcoded real credentials exist in the repository.
- No secrets are exposed in frontend bundles.
- Real credentials are stored using Windows Credential Manager.
- SQLite contains references and metadata only.
- `.env.example` contains placeholders only.
- Real secret files are excluded from Git.
- Logs redact sensitive values.
- Credential management is handled by the backend.
- Tests use fake credentials and verify secret redaction.
- Missing credentials produce a clear configuration error, not a hardcoded fallback.

## 13. Priority

These rules are mandatory and apply to every implementation phase.

If another instruction conflicts with this document, credential security takes priority. Ask the user before implementing a design that would require storing or exposing sensitive information.