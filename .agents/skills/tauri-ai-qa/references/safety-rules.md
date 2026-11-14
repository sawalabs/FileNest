
# Safety Rules

Default to read-only and reversible testing.

Require explicit approval before:

- Deleting data
- Overwriting files
- Resetting databases
- Changing security settings
- Installing dependencies
- Changing project configuration
- Running production migrations
- Submitting real transactions
- Sending external messages

Use synthetic data and disposable test accounts.

Never bypass authentication.

Never expose secrets.

Never claim a test passed without observing its result.
