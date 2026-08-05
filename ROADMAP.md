# Project Roadmap

Library Ticket Booker is a local-first automation app for reserving free museum and attraction passes through KCLS and SPL.

## V1: Complete

- Provider-aware KCLS and SPL booking flows
- Separate provider credentials from `.env`
- Separate provider schedules:
  - SPL at `12:00`, 30-day window
  - KCLS at `14:00`, 14-day window
- Live pass catalog refresh for both providers
- Desired bookings with provider, visit date, pass name, and priority
- Automatic next-priority defaults in the dashboard
- One successful booking per provider/month before skipping backups
- Guarded live mode with `LIBRARY_ALLOW_LIVE_SUBMIT=0`
- Real submit mode with `LIBRARY_ALLOW_LIVE_SUBMIT=1`
- Local dashboard for schedules, rules, desired bookings, pass catalogs, upcoming passes, and recent attempts
- Attempt logging to ignored local `data/results.jsonl`
- SMTP email notifications for live success/failure summaries
- Unit tests for planning, parsing, logging, notifications, and dashboard helpers

## Next Milestone: Deployment

- Create an Oracle Cloud VM
- Install Python, project dependencies, and Playwright Chromium
- Add `.env` on the VM without committing it
- Configure Pacific-time cron entries:
  - SPL shortly after noon
  - KCLS shortly after 2 p.m.
- Confirm cron logs and email notifications
- Document the full Oracle setup with screenshots or exact commands

## Short-Term Improvements

- Add dashboard buttons to refresh KCLS and SPL pass catalogs
- Improve failure classification:
  - no availability
  - login failed
  - missing email/credentials
  - monthly limit reached
  - form selector changed
- Add a startup/preflight check for required credentials, notification config, and Playwright installation
- Add a simple CLI command for validating `.env` without printing secrets
- Improve Recent Attempts filtering by provider/status/date

## Future Improvements

- Sync currently booked passes from KCLS and SPL library accounts, then use live account state for the dashboard's Upcoming Passes section so manual cancellations do not leave stale bookings visible.
- Scrape available dates and compare them against desired bookings before attempting reservations.
- Add richer notification channels, such as SMS, Slack, or Discord.
- Package a cloud deployment guide for Oracle Cloud, systemd, and cron.
- Add robust handling for rate limits, timeouts, provider downtime, and LibCal UI changes.
- Consider a hosted dashboard only if remote access becomes necessary.

## Security Notes

- Keep `.env`, `data/desired_bookings.json`, `data/results.jsonl`, and `artifacts/` out of Git.
- Do not commit real screenshots or HTML artifacts from authenticated sessions.
- Prefer provider-specific app passwords or SMTP credentials over personal account passwords.
- Consider using a GitHub noreply email before publishing if commit author privacy matters.
