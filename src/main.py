import argparse
from datetime import datetime, timedelta
import time
from typing import Any

from src.booker import LibraryAccount, attempt_bookings, fetch_live_passes, inspect_reservation_site
from src.config import load_config, load_dates, load_desired_bookings, load_passes, save_passes
from src.notifier import send_test_email, notify_attempt_summary

SUPPORTED_PROVIDERS = ("kcls", "spl")
FAST_SCHEDULER_POLL_SECONDS = 0.25
FAST_SCHEDULER_WINDOW_SECONDS = 60
NORMAL_SCHEDULER_POLL_SECONDS = 10
SCHEDULER_RUN_WINDOW_MINUTES = 1


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


def merge_provider_passes(
    existing_passes: list[dict[str, Any]],
    refreshed_passes: list[dict[str, Any]],
    provider: str,
) -> list[dict[str, Any]]:
    provider_key = provider.casefold()
    retained = [item for item in existing_passes if str(item.get("provider", "kcls")).casefold() != provider_key]
    return retained + refreshed_passes


def get_provider_schedule(config: Any, provider: str):
    schedules = getattr(config, "schedules", {})
    return schedules.get(provider, config.scheduler)


def build_booking_plan(
    desired_bookings: list[dict[str, Any]],
    passes: list[dict[str, Any]],
    days_ahead: int,
    provider: str | None = None,
) -> list[tuple[dict[str, Any], datetime]]:
    target_dates = {item.isoformat() for item in compute_target_dates([str(item.get("date", "")) for item in desired_bookings], days_ahead)}
    plan: list[tuple[dict[str, Any], datetime]] = []
    requested_provider = provider.casefold() if provider else None

    for booking in sorted(
        desired_bookings,
        key=lambda item: (item.get("provider", "kcls"), item.get("date", ""), int(item.get("priority", 9999))),
    ):
        date_text = str(booking.get("date", ""))
        if date_text not in target_dates:
            continue

        provider = str(booking.get("provider", "kcls")).casefold()
        if requested_provider and provider != requested_provider:
            continue
        if provider not in SUPPORTED_PROVIDERS:
            print(f"Skipping unsupported provider {provider}: {booking.get('pass_name')}")
            continue

        pass_info = find_pass_by_name(passes, str(booking.get("pass_name", "")), provider=provider)
        if pass_info is None:
            print(f"Skipping unknown pass: {booking.get('pass_name')}")
            continue

        plan.append((pass_info, datetime.fromisoformat(date_text).date()))

    return plan


def build_booking_plan_for_config(
    desired_bookings: list[dict[str, Any]],
    passes: list[dict[str, Any]],
    config: Any,
    provider: str | None = None,
) -> list[tuple[dict[str, Any], datetime]]:
    providers = [provider.casefold()] if provider else list(SUPPORTED_PROVIDERS)
    plan: list[tuple[dict[str, Any], datetime]] = []
    for provider_key in providers:
        schedule = get_provider_schedule(config, provider_key)
        plan.extend(
            build_booking_plan(
                desired_bookings,
                passes,
                schedule.days_ahead,
                provider=provider_key,
            )
        )
    return plan


def visit_month_key(target_date) -> str:
    return target_date.strftime("%Y-%m")


def run_once(config, dry_run: bool = False, provider: str | None = None):
    passes = load_passes()
    desired_bookings = load_desired_bookings()

    if desired_bookings:
        booking_plan = build_booking_plan_for_config(desired_bookings, passes, config, provider=provider)
    else:
        dates = load_dates()
        providers = [provider.casefold()] if provider else list(SUPPORTED_PROVIDERS)
        booking_plan = []
        for provider_key in providers:
            schedule = get_provider_schedule(config, provider_key)
            target_dates = compute_target_dates(dates, schedule.days_ahead)
            booking_plan.extend(
                (pass_info, target_date)
                for target_date in target_dates
                for pass_info in passes
                if str(pass_info.get("provider", "kcls")).casefold() == provider_key
            )

    if not booking_plan:
        provider_label = provider.upper() if provider else "configured providers"
        print(f"No matching dates for {provider_label}.")
        return

    booked_months: set[str] = set()
    all_results_by_provider: dict[str, list[Any]] = {}

    print("Booking plan:")
    for pass_info, target_date in booking_plan:
        print(f"- {target_date.isoformat()}: {pass_info.get('provider', 'kcls').upper()} - {pass_info['name']}")

    for pass_info, target_date in booking_plan:
        provider_key = str(pass_info.get("provider", "kcls")).casefold()
        month_key = f"{provider_key}:{visit_month_key(target_date)}"
        if month_key in booked_months:
            print(f"Skipping {pass_info['name']} on {target_date}: already booked a {provider_key} pass for {visit_month_key(target_date)}.")
            continue

        account_config = getattr(config, "accounts", {}).get(provider_key, config.account)
        account = LibraryAccount(
            card_number=account_config.card_number,
            pin=account_config.pin,
            email=account_config.email,
        )

        results = attempt_bookings(
            account=account,
            passes=[pass_info],
            dates=[target_date],
            dry_run=dry_run,
        )
        all_results_by_provider.setdefault(provider_key, []).extend(result for _, result in results)

        for request, result in results:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"{request.pass_info['name']} on {request.target_date}: {status} - {result.message}")
            if result.success:
                booked_months.add(month_key)

    if not dry_run:
        for provider_key, results in all_results_by_provider.items():
            notify_attempt_summary(provider_key, results)


def show_plan(config, provider: str | None = None) -> None:
    passes = load_passes()
    desired_bookings = load_desired_bookings()

    if desired_bookings:
        booking_plan = build_booking_plan_for_config(desired_bookings, passes, config, provider=provider)
    else:
        dates = load_dates()
        providers = [provider.casefold()] if provider else list(SUPPORTED_PROVIDERS)
        booking_plan = []
        for provider_key in providers:
            schedule = get_provider_schedule(config, provider_key)
            target_dates = compute_target_dates(dates, schedule.days_ahead)
            booking_plan.extend(
                (pass_info, target_date)
                for target_date in target_dates
                for pass_info in passes
                if str(pass_info.get("provider", "kcls")).casefold() == provider_key
            )

    print(f"Today: {datetime.now().date().isoformat()}")
    for provider_key in ([provider.casefold()] if provider else list(SUPPORTED_PROVIDERS)):
        schedule = get_provider_schedule(config, provider_key)
        print(f"{provider_key.upper()}: run time {schedule.run_time}, booking window {schedule.days_ahead} days ahead")

    if not booking_plan:
        print("No bookings match today's release window.")
        return

    print("Bookings that match today's release window:")
    for pass_info, target_date in booking_plan:
        print(f"- {target_date.isoformat()}: {pass_info.get('provider', 'kcls').upper()} - {pass_info['name']}")


def next_release_time(now: datetime, run_time: str) -> datetime:
    target = datetime.combine(now.date(), datetime.strptime(run_time, "%H:%M").time())
    if now >= target + timedelta(minutes=SCHEDULER_RUN_WINDOW_MINUTES):
        target += timedelta(days=1)
    return target


def scheduler_sleep_seconds(config, providers: list[str], now: datetime) -> float:
    seconds_until_release = min(
        (next_release_time(now, get_provider_schedule(config, provider_key).run_time) - now).total_seconds()
        for provider_key in providers
    )
    if seconds_until_release <= FAST_SCHEDULER_WINDOW_SECONDS:
        return FAST_SCHEDULER_POLL_SECONDS
    return min(
        NORMAL_SCHEDULER_POLL_SECONDS,
        max(FAST_SCHEDULER_POLL_SECONDS, seconds_until_release - FAST_SCHEDULER_WINDOW_SECONDS),
    )


def run_scheduler(config, dry_run: bool = False, provider: str | None = None):
    providers = [provider.casefold()] if provider else list(SUPPORTED_PROVIDERS)
    print("Scheduler started:")
    for provider_key in providers:
        schedule = get_provider_schedule(config, provider_key)
        print(f"- {provider_key.upper()} daily at {schedule.run_time}")

    completed_runs: set[tuple[str, str]] = set()
    while True:
        now = datetime.now()
        for provider_key in providers:
            schedule = get_provider_schedule(config, provider_key)
            target = datetime.combine(now.date(), datetime.strptime(schedule.run_time, "%H:%M").time())
            run_key = (provider_key, target.date().isoformat())
            if now >= target and now < target + timedelta(minutes=SCHEDULER_RUN_WINDOW_MINUTES) and run_key not in completed_runs:
                print(f"Running scheduled {provider_key.upper()} booking task...")
                run_once(config, dry_run=dry_run, provider=provider_key)
                completed_runs.add(run_key)

        time.sleep(scheduler_sleep_seconds(config, providers, datetime.now()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Library pass requester")
    parser.add_argument("--run-once", action="store_true", help="Run the booking flow one time")
    parser.add_argument("--show-plan", action="store_true", help="Print bookings that match today's release window")
    parser.add_argument("--schedule", action="store_true", help="Run continuously and execute at the configured time")
    parser.add_argument("--web", action="store_true", help="Run the local web dashboard")
    parser.add_argument("--inspect-live-site", action="store_true", help="Capture live reservation pages for selector work")
    parser.add_argument("--refresh-passes", action="store_true", help="Refresh pass options from a live pass directory")
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, help="Limit booking, refresh, or inspection to one provider")
    parser.add_argument("--headed", action="store_true", help="Show the browser for Playwright commands")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the local web dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local web dashboard")
    parser.add_argument("--dry-run", action="store_true", help="Simulate bookings without opening a browser")
    parser.add_argument("--send-test-email", action="store_true", help="Send a test notification email using SMTP settings")
    args = parser.parse_args()

    config = load_config()

    if args.run_once:
        run_once(config, dry_run=args.dry_run, provider=args.provider)
    elif args.show_plan:
        show_plan(config, provider=args.provider)
    elif args.schedule:
        run_scheduler(config, dry_run=args.dry_run, provider=args.provider)
    elif args.send_test_email:
        if send_test_email():
            print("Test email sent.")
    elif args.inspect_live_site:
        artifacts = inspect_reservation_site(provider=args.provider or "kcls", headless=not args.headed)
        for label, path in artifacts.items():
            print(f"{label}: {path}")
    elif args.refresh_passes:
        provider = args.provider or "kcls"
        refreshed = fetch_live_passes(provider=provider, headless=not args.headed)
        passes = merge_provider_passes(load_passes(), refreshed, provider=provider)
        save_passes(passes)
        print(f"Saved {len(refreshed)} {provider.upper()} passes to data/passes.json")
    elif args.web:
        from src.web_app import run_web_server

        run_web_server(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
