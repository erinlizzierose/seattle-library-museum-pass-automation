# Library Ticket Booker

A small Python automation project to help reserve KCLS and Seattle Public Library museum passes on the daily release window.

## What this does

- Loads a list of desired passes and reservation dates
- Computes which dates are available 14 days in the future
- Runs a booking attempt at 2pm local time
- Provides a local web dashboard for editing passes/dates and reviewing attempts
- Logs each booking attempt to `data/results.jsonl`
- Can refresh real KCLS and SPL pass options from their LibCal pass directories
- Uses Playwright for live LibCal booking pages
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
   KCLS_LIBRARY_CARD_NUMBER=...
   KCLS_LIBRARY_PIN=...
   KCLS_LIBRARY_EMAIL=...

   SPL_LIBRARY_CARD_NUMBER=...
   SPL_LIBRARY_PIN=...
   SPL_LIBRARY_EMAIL=...

   LIBRARY_ALLOW_LIVE_SUBMIT=0

   NOTIFY_EMAIL_TO=...
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=...
   SMTP_PASSWORD=...
   SMTP_FROM=...
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

## Live Provider Setup

Install Playwright support:

```bash
python -m pip install -e ".[automation]"
python -m playwright install chromium
```

Refresh the real pass list:

```bash
python -m src.main --refresh-passes --provider kcls
python -m src.main --refresh-passes --provider spl
```

Capture live pages for debugging selectors:

```bash
python -m src.main --inspect-live-site --provider kcls
python -m src.main --inspect-live-site --provider spl
```

Live booking is guarded. By default, the bot stops before the final reservation submission and saves screenshots/HTML under `artifacts/`. To allow final submission, set this in `.env` only when you are ready:

```bash
LIBRARY_ALLOW_LIVE_SUBMIT=1
```

## Dashboard

The local dashboard lets you:

- View upcoming passes from successful future booking attempts
- Add or remove desired bookings with pass, date, and priority
- Add or remove passes
- Review recent booking attempts
- Run a dry booking attempt without launching a browser

Passes added through the dashboard still need real booking selectors before live automation can reserve them. Use dry-run mode while setting up pass data.

## Notifications

The app sends notification email directly from Python using SMTP settings in `.env`; Oracle Cloud only runs the script on schedule.

Required settings:

```bash
NOTIFY_EMAIL_ENABLED=1
NOTIFY_EMAIL_TO=your_email@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your_email@example.com
```

For Gmail, use an app password rather than your normal Google password. If SMTP settings are missing, booking still runs and the app prints that notifications were skipped.

After adding SMTP settings, send a test email:

```bash
.venv/bin/python -m src.main --send-test-email
```

The app sends an email after live provider attempts:

- Success: the booked pass, provider, visit date, and attempt details.
- Failure: a summary that no pass was booked and each attempted pass result.
- No matching booking plan: no email.
- Dry runs: no email.

## Desired Bookings

Use `data/desired_bookings.json` for your personal booking queue. The pass catalog in `data/passes.json` can stay as the full provider-tagged KCLS/SPL list.

Create your local queue from the example:

```bash
cp data/desired_bookings.example.json data/desired_bookings.json
```

`data/desired_bookings.json` is ignored by Git so you do not publish your personal booking plans.

Example:

```json
[
  {
    "date": "2026-07-20",
    "pass_name": "Woodland Park Zoo",
    "priority": 1,
    "provider": "kcls"
  },
  {
    "date": "2026-07-20",
    "pass_name": "MOPOP",
    "priority": 2,
    "provider": "kcls"
  }
]
```

For each visit month, lower priority numbers run first. Once a booking succeeds for a month, later backup choices for that same visit month are skipped. This matches KCLS's one museum pass per calendar month limit, based on the museum visit date.

The dashboard separates KCLS and SPL desired bookings. Both providers use separate pass lists and separate credentials. A successful booking skips later backup choices for the same provider and visit month.

## Library Rules

KCLS:

- New passes are released daily at 2 p.m.
- Passes are available 2 weeks into the future.
- The default local run time is `14:00`.
- You can reserve one museum pass per calendar month, counted by visit date.
- A reserved but unused pass still counts against the monthly limit.

SPL:

- New passes are available daily after 12 p.m.
- The reservation system shows available passes for the next 30 days.
- The default local run time is `12:00`.
- Each library card holder can reserve one pass per calendar month, counted by visit date.
- Bring the printed or electronic pass and photo ID on the selected visit date.

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

Example cron entries:

```cron
2 12 * * * cd /home/ubuntu/library-tool && /home/ubuntu/library-tool/.venv/bin/python -m src.main --run-once --provider spl >> /home/ubuntu/library-tool/logs/spl-booking.log 2>&1
2 14 * * * cd /home/ubuntu/library-tool && /home/ubuntu/library-tool/.venv/bin/python -m src.main --run-once --provider kcls >> /home/ubuntu/library-tool/logs/kcls-booking.log 2>&1
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
