from dataclasses import dataclass
from datetime import date
from typing import Any, List, Tuple
import os

from src.results import AttemptResult, append_attempt, create_attempt_result


@dataclass
class BookingRequest:
    pass_info: dict[str, Any]
    target_date: date


def _ensure_playwright_installed() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install with `python -m pip install -e .[automation]` and run `playwright install`."
        ) from exc


def _launch_browser():
    from playwright.sync_api import Browser, Page, sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    return playwright, browser, context, page


def login(page: Any, username: str, password: str) -> bool:
    """Perform the sign-in process in a browser session."""
    print(f"Logging in as {username}")

    # TODO: Update these selectors and URLs for the actual library login page.
    try:
        page.goto("https://www.kingcounty.gov/library/login")
        page.fill("input[name='username']", username)
        page.fill("input[name='password']", password)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle", timeout=15000)

        # Try a few heuristics to detect successful login.
        try:
            page.wait_for_selector("text=Sign out", timeout=5000)
            return True
        except Exception:
            # Fallback: check for common account/profile URL fragments
            url = page.url or ""
            if any(fragment in url for fragment in ("/account", "/profile", "my-account")):
                return True

        # As a last resort assume failure
        return False
    except Exception:
        return False


def book_pass_for_date(page: Any, request: BookingRequest, dry_run: bool = False) -> tuple[bool, str]:
    """Attempt a single pass booking in the browser.

    This function provides a small, configurable skeleton that navigates to a
    pass URL (if provided in `pass_info`) and tries to perform selection/submission
    using optional selector keys. For real automation, populate `pass_info` with
    `url`, `select_selector`, `date_selector`, `submit_selector`, and
    `success_selector` as appropriate.
    """
    name = request.pass_info.get("name", "<unnamed>")
    print(f"Attempting booking: {name} for {request.target_date}")

    if dry_run:
        print(f"Dry-run: would attempt booking for {name} on {request.target_date}")
        return True, "Dry-run simulated successfully"

    try:
        url = request.pass_info.get("url")
        if url:
            page.goto(url)

        select = request.pass_info.get("select_selector")
        if select:
            try:
                page.click(select)
            except Exception:
                pass

        date_selector = request.pass_info.get("date_selector")
        if date_selector:
            try:
                # Many widgets expect a visible formatted date; use ISO by default
                page.fill(date_selector, request.target_date.isoformat())
            except Exception:
                pass

        submit = request.pass_info.get("submit_selector")
        if submit:
            try:
                page.click(submit)
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

        success_sel = request.pass_info.get("success_selector")
        if success_sel:
            try:
                page.wait_for_selector(success_sel, timeout=5000)
                return True, "Reservation confirmation was detected"
            except Exception as exc:
                return False, f"Success confirmation was not detected: {exc}"

        # No success selector provided; assume we failed to confirm booking.
        return False, "No success selector configured, so booking could not be confirmed"
    except Exception as exc:
        return False, f"Booking attempt failed: {exc}"


def attempt_bookings(
    username: str,
    password: str,
    passes: list[dict[str, Any]],
    dates: list[date],
    dry_run: bool = False,
) -> List[Tuple[BookingRequest, AttemptResult]]:
    # Allow enabling dry-run via environment as well: set LIBRARY_DRY_RUN=1
    env_dry = os.environ.get("LIBRARY_DRY_RUN", "0") == "1"
    dry_run = dry_run or env_dry

    playwright = None
    browser = None
    context = None
    page = None

    if dry_run:
        print("Dry-run enabled: simulating booking attempts (no browser launched)")
        results: List[Tuple[BookingRequest, AttemptResult]] = []
        for pass_info in passes:
            for target_date in dates:
                request = BookingRequest(pass_info=pass_info, target_date=target_date)
                result = create_attempt_result(
                    pass_info=pass_info,
                    target_date=target_date,
                    success=True,
                    dry_run=True,
                    message="Dry-run simulated successfully",
                )
                append_attempt(result)
                results.append((request, result))
        return results

    _ensure_playwright_installed()

    try:
        playwright, browser, context, page = _launch_browser()

        if not login(page, username, password):
            raise RuntimeError("Login failed")

        results: List[Tuple[BookingRequest, AttemptResult]] = []
        for pass_info in passes:
            for target_date in dates:
                request = BookingRequest(pass_info=pass_info, target_date=target_date)
                success, message = book_pass_for_date(page, request, dry_run=False)
                result = create_attempt_result(
                    pass_info=pass_info,
                    target_date=target_date,
                    success=success,
                    dry_run=False,
                    message=message,
                )
                append_attempt(result)
                results.append((request, result))

        return results
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
