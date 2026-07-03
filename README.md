# Library Ticket Booker

A small Python automation project to help reserve King County library passes on the daily 2pm release.

## What this does

- Loads a list of desired passes and reservation dates
- Computes which dates are available 14 days in the future
- Runs a booking attempt at 2pm local time
- Provides a local web dashboard for editing passes/dates and reviewing attempts
- Logs each booking attempt to `data/results.jsonl`
- Keeps automation logic separate from the local UI

## Files

- `.env.example` — environment variable template for secrets
- `config.yaml` — scheduler settings
- `data/passes.json` — desired pass list
- `data/dates.json` — desired reservation dates
- `src/main.py` — CLI entry point and scheduler
- `src/config.py` — config + data loading
- `src/booker.py` — booking workflow placeholder
- `src/results.py` — booking attempt logging
- `src/web_app.py` — local web dashboard

## Quick start

1. Create a Python virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   python -m pip install -U pip
   python -m pip install -e .
   ```

3. Copy `.env.example` to `.env` and update your username/password; then update `config.yaml`, `data/passes.json`, and `data/dates.json`.

4. Run once:

   ```bash
   python -m src.main --run-once
   ```

5. Run the scheduler:
   ```bash
   python -m src.main --schedule
   ```

6. Run the local dashboard:
   ```bash
   python -m src.main --web
   ```

   Then open `http://127.0.0.1:8000`.

## Dashboard

The local dashboard lets you:

- Add or remove desired reservation dates
- Add or remove passes
- Review recent booking attempts
- Run a dry booking attempt without launching a browser

Passes added through the dashboard still need real booking selectors before live automation can reserve them. Use dry-run mode while setting up pass data.

## Cloud deployment notes

A cloud VM is a good fit since the script should run reliably at 2pm each day. On a VM, you can use systemd, cron, or a long-running terminal session.
