# Security

This project is designed to keep personal credentials and booking history out of version control.

## Do Not Commit

- `.env`
- library card numbers
- library PINs
- SMTP usernames/passwords
- Gmail app passwords
- `data/desired_bookings.json`
- `data/results.jsonl`
- Playwright HTML/screenshot artifacts from authenticated sessions

These paths are ignored by `.gitignore` where applicable.

## Before Publishing

Run:

```bash
git status --short
git ls-files | rg '(^\.env$|desired_bookings\.json$|results\.jsonl$|artifacts/)'
```

The second command should print nothing.

Also remember that Git commit metadata can include your configured author name and email. Use a GitHub noreply address if that matters for your public profile.

## Credentials

Use provider-specific environment variables:

- `KCLS_LIBRARY_CARD_NUMBER`
- `KCLS_LIBRARY_PIN`
- `SPL_LIBRARY_CARD_NUMBER`
- `SPL_LIBRARY_PIN`

For Gmail notifications, use a Google app password instead of your normal Google password.

If a secret is accidentally exposed, revoke or rotate it immediately.
