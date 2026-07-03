import argparse
from datetime import datetime, timedelta
import time

from src.booker import attempt_bookings
from src.config import load_config, load_dates, load_passes


def compute_target_dates(dates: list[str], days_ahead: int) -> list[datetime]:
    today = datetime.now().date()
    target_day = today + timedelta(days=days_ahead)
    selected_dates = []

    for date_text in dates:
        desired_date = datetime.fromisoformat(date_text).date()
        if desired_date == target_day:
            selected_dates.append(desired_date)

    return selected_dates


def run_once(config, dry_run: bool = False):
    passes = load_passes()
    dates = load_dates()
    target_dates = compute_target_dates(dates, config.scheduler.days_ahead)

    if not target_dates:
        print("No matching dates are exactly" , config.scheduler.days_ahead, "days ahead.")
        return

    print("Booking for dates:", [d.isoformat() for d in target_dates])
    results = attempt_bookings(
        username=config.login.username,
        password=config.login.password,
        passes=passes,
        dates=target_dates,
        dry_run=dry_run,
    )

    for request, result in results:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"{request.pass_info['name']} on {request.target_date}: {status} - {result.message}")


def run_scheduler(config, dry_run: bool = False):
    run_time = config.scheduler.run_time
    print(f"Scheduler started, will run daily at {run_time}")

    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), datetime.strptime(run_time, "%H:%M").time())
        if now >= target and now < target + timedelta(minutes=1):
            print("Running scheduled booking task...")
            run_once(config, dry_run=dry_run)
            time.sleep(61)
        else:
            time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Library pass requester")
    parser.add_argument("--run-once", action="store_true", help="Run the booking flow one time")
    parser.add_argument("--schedule", action="store_true", help="Run continuously and execute at the configured time")
    parser.add_argument("--web", action="store_true", help="Run the local web dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the local web dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local web dashboard")
    parser.add_argument("--dry-run", action="store_true", help="Simulate bookings without opening a browser")
    args = parser.parse_args()

    config = load_config()

    if args.run_once:
        run_once(config, dry_run=args.dry_run)
    elif args.schedule:
        run_scheduler(config, dry_run=args.dry_run)
    elif args.web:
        from src.web_app import run_web_server

        run_web_server(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
