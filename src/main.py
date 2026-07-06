import argparse
from datetime import datetime, timedelta
import time
from typing import Any

from src.booker import LibraryAccount, attempt_bookings, fetch_live_passes, inspect_reservation_site
from src.config import load_config, load_dates, load_desired_bookings, load_passes, save_passes


def compute_target_dates(dates: list[str], days_ahead: int) -> list[datetime]:
    today = datetime.now().date()
    target_day = today + timedelta(days=days_ahead)
    selected_dates = []

    for date_text in dates:
        desired_date = datetime.fromisoformat(date_text).date()
        if desired_date == target_day:
            selected_dates.append(desired_date)

    return selected_dates


def find_pass_by_name(passes: list[dict[str, Any]], pass_name: str, provider: str = "kcls") -> dict[str, Any] | None:
    wanted = pass_name.casefold()
    for pass_info in passes:
        if str(pass_info.get("provider", "kcls")).casefold() != provider.casefold():
            continue
        if str(pass_info.get("name", "")).casefold() == wanted:
            return pass_info
    return None


def build_booking_plan(
    desired_bookings: list[dict[str, Any]],
    passes: list[dict[str, Any]],
    days_ahead: int,
) -> list[tuple[dict[str, Any], datetime]]:
    target_dates = {item.isoformat() for item in compute_target_dates([str(item.get("date", "")) for item in desired_bookings], days_ahead)}
    plan: list[tuple[dict[str, Any], datetime]] = []

    for booking in sorted(
        desired_bookings,
        key=lambda item: (item.get("provider", "kcls"), item.get("date", ""), int(item.get("priority", 9999))),
    ):
        date_text = str(booking.get("date", ""))
        if date_text not in target_dates:
            continue

        provider = str(booking.get("provider", "kcls"))
        if provider != "kcls":
            print(f"Skipping {provider} booking until that provider is implemented: {booking.get('pass_name')}")
            continue

        pass_info = find_pass_by_name(passes, str(booking.get("pass_name", "")), provider=provider)
        if pass_info is None:
            print(f"Skipping unknown pass: {booking.get('pass_name')}")
            continue

        plan.append((pass_info, datetime.fromisoformat(date_text).date()))

    return plan


def visit_month_key(target_date) -> str:
    return target_date.strftime("%Y-%m")


def run_once(config, dry_run: bool = False):
    passes = load_passes()
    desired_bookings = load_desired_bookings()

    if desired_bookings:
        booking_plan = build_booking_plan(desired_bookings, passes, config.scheduler.days_ahead)
    else:
        dates = load_dates()
        target_dates = compute_target_dates(dates, config.scheduler.days_ahead)
        booking_plan = [(pass_info, target_date) for target_date in target_dates for pass_info in passes]

    if not booking_plan:
        print("No matching dates are exactly" , config.scheduler.days_ahead, "days ahead.")
        return

    account = LibraryAccount(
        card_number=config.account.card_number,
        pin=config.account.pin,
        email=config.account.email,
    )
    booked_months: set[str] = set()

    print("Booking plan:")
    for pass_info, target_date in booking_plan:
        print(f"- {target_date.isoformat()}: {pass_info['name']}")

    for pass_info, target_date in booking_plan:
        provider_key = str(pass_info.get("provider", "kcls"))
        month_key = f"{provider_key}:{visit_month_key(target_date)}"
        if month_key in booked_months:
            print(f"Skipping {pass_info['name']} on {target_date}: already booked a {provider_key} pass for {visit_month_key(target_date)}.")
            continue

        results = attempt_bookings(
            account=account,
            passes=[pass_info],
            dates=[target_date],
            dry_run=dry_run,
        )

        for request, result in results:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"{request.pass_info['name']} on {request.target_date}: {status} - {result.message}")
            if result.success:
                booked_months.add(month_key)


def show_plan(config) -> None:
    passes = load_passes()
    desired_bookings = load_desired_bookings()

    if desired_bookings:
        booking_plan = build_booking_plan(desired_bookings, passes, config.scheduler.days_ahead)
    else:
        dates = load_dates()
        target_dates = compute_target_dates(dates, config.scheduler.days_ahead)
        booking_plan = [(pass_info, target_date) for target_date in target_dates for pass_info in passes]

    print(f"Today: {datetime.now().date().isoformat()}")
    print(f"Booking window: {config.scheduler.days_ahead} days ahead")
    print(f"Configured run time: {config.scheduler.run_time}")

    if not booking_plan:
        print("No bookings match today's release window.")
        return

    print("Bookings that match today's release window:")
    for pass_info, target_date in booking_plan:
        print(f"- {target_date.isoformat()}: {pass_info['name']}")


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
    parser.add_argument("--show-plan", action="store_true", help="Print bookings that match today's release window")
    parser.add_argument("--schedule", action="store_true", help="Run continuously and execute at the configured time")
    parser.add_argument("--web", action="store_true", help="Run the local web dashboard")
    parser.add_argument("--inspect-live-site", action="store_true", help="Capture live KCLS reservation pages for selector work")
    parser.add_argument("--refresh-passes", action="store_true", help="Refresh pass options from the live KCLS pass directory")
    parser.add_argument("--headed", action="store_true", help="Show the browser for Playwright commands")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the local web dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local web dashboard")
    parser.add_argument("--dry-run", action="store_true", help="Simulate bookings without opening a browser")
    args = parser.parse_args()

    config = load_config()

    if args.run_once:
        run_once(config, dry_run=args.dry_run)
    elif args.show_plan:
        show_plan(config)
    elif args.schedule:
        run_scheduler(config, dry_run=args.dry_run)
    elif args.inspect_live_site:
        artifacts = inspect_reservation_site(headless=not args.headed)
        for label, path in artifacts.items():
            print(f"{label}: {path}")
    elif args.refresh_passes:
        passes = fetch_live_passes(headless=not args.headed)
        save_passes(passes)
        print(f"Saved {len(passes)} passes to data/passes.json")
    elif args.web:
        from src.web_app import run_web_server

        run_web_server(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
