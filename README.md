# Library Ticket Booker

A small Python automation project to help reserve King County library passes on the daily 2pm release.

## What this does

- Loads a list of desired passes and reservation dates
- Computes which dates are available 14 days in the future
- Runs a booking attempt at 2pm local time
- Provides a local web dashboard for editing passes/dates and reviewing attempts
- Logs each booking attempt to `data/results.jsonl`
- Can refresh real KCLS pass options from `https://rooms.kcls.org/passes`
- Uses Playwright for live KCLS/LibCal booking pages
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

3. Copy `.env.example` to `.env` and update your library card details; then update `config.yaml`, `data/passes.json`, and `data/dates.json`.

   ```bash
   LIBRARY_CARD_NUMBER=...
   LIBRARY_PIN=...
   LIBRARY_EMAIL=...
   LIBRARY_ALLOW_LIVE_SUBMIT=0
   ```

   Keep `LIBRARY_ALLOW_LIVE_SUBMIT=0` while testing. The bot will authenticate and prepare the reservation flow, but stop before final submission.

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

## Live KCLS Setup

Install Playwright support:

```bash
python -m pip install -e ".[automation]"
python -m playwright install chromium
```

Refresh the real pass list:

```bash
python -m src.main --refresh-passes
```

Capture live KCLS pages for debugging selectors:

```bash
python -m src.main --inspect-live-site
```

Live booking is guarded. By default, the bot stops before the final reservation submission and saves screenshots/HTML under `artifacts/`. To allow final submission, set this in `.env` only when you are ready:

```bash
LIBRARY_ALLOW_LIVE_SUBMIT=1
```

## Dashboard

The local dashboard lets you:

- Add or remove desired bookings with pass, date, and priority
- Add or remove passes
- Review recent booking attempts
- Run a dry booking attempt without launching a browser

Passes added through the dashboard still need real booking selectors before live automation can reserve them. Use dry-run mode while setting up pass data.

## Desired Bookings

Use `data/desired_bookings.json` for your personal booking queue. The pass catalog in `data/passes.json` can stay as the full KCLS list.

Example:

```json
[
  {
    "date": "2026-07-20",
    "pass_name": "Woodland Park Zoo",
    "priority": 1
  },
  {
    "date": "2026-07-20",
    "pass_name": "MOPOP",
    "priority": 2
  }
]
```

For each visit date, lower priority numbers run first. Once a booking succeeds for a date, later backup choices for that same date are skipped.

Check what would run today:

```bash
.venv/bin/python -m src.main --show-plan
```

Run one guarded attempt:

```bash
.venv/bin/python -m src.main --run-once
```

Leave `LIBRARY_ALLOW_LIVE_SUBMIT=0` until you are ready for the app to click the final Reserve button.

## Oracle Cloud Cron Deployment

On an Ubuntu VM, install the app, then add a cron entry that runs shortly after 2pm Pacific and writes logs.

Example cron entry:

```cron
2 14 * * * cd /home/ubuntu/library-tool && /home/ubuntu/library-tool/.venv/bin/python -m src.main --run-once >> /home/ubuntu/library-tool/logs/booking.log 2>&1
```

Use the VM's local timezone or set the cron timezone explicitly. Check it with:

```bash
date
timedatectl
```

For the simplest setup, set the VM timezone to Pacific time:

```bash
sudo timedatectl set-timezone America/Los_Angeles
```

View installed cron jobs:

```bash
crontab -l
```

Confirm cron ran:

```bash
tail -100 logs/booking.log
```

You can also run a one-minute test cron before the real booking day:

```cron
* * * * * cd /home/ubuntu/library-tool && /home/ubuntu/library-tool/.venv/bin/python -m src.main --show-plan >> /home/ubuntu/library-tool/logs/cron-test.log 2>&1
```

Wait a minute, check `logs/cron-test.log`, then remove the test entry.

## Cloud deployment notes

A cloud VM is a good fit since the script should run reliably at 2pm each day. On a VM, you can use systemd, cron, or a long-running terminal session.
