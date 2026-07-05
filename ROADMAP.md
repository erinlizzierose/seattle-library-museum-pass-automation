# Project Roadmap

This project is starting as a scheduler-enabled booking helper for King County library passes.

## Current MVP goals

- Load desired passes from `data/passes.json`
- Load desired reservation dates from `data/dates.json`
- Run once or as a daily scheduler at 2pm
- Use environment variables for credentials via `.env`
- Keep booking logic separate from the scheduler
- Provide a local dashboard for managing passes/dates and reviewing attempts
- Log booking attempts to `data/results.jsonl`
- Refresh real KCLS pass options from the live pass directory
- Resolve available booking links from the live date-based KCLS page
- Authenticate with library card number and PIN through LibAuth

## Short-term additions

- Finish and verify the post-auth reservation form submission flow
- Add retry logic for failed booking attempts
- Add notifications for success/failure (email, Slack, etc.)
- Add validation for credentials and target dates before live runs
- Add a UI control to refresh passes from KCLS

## Future improvements

- Scrape available dates and compare against desired dates
- Add a CLI for managing desired passes and dates
- Replace the local dashboard with a richer web app if remote access is needed
- Add a cloud deployment guide for running on a VM
- Add robust error handling for rate limits, timeouts, and site changes

## Notes

- Start with a manual pass list and scheduler.
- Add dynamic scraping only after the core booking flow works.
- Keep automation separate from any UI so the backend can be reused later.
