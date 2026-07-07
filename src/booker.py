from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, List, Tuple
from urllib.parse import urljoin
import os
import re

from src.results import AttemptResult, append_attempt, create_attempt_result


KCLS_RESERVE_BY_LOCATION_URL = "https://rooms.kcls.org/passes"
KCLS_RESERVE_BY_DATE_URL = "https://rooms.kcls.org/admission"
SPL_RESERVE_BY_LOCATION_URL = "https://spl.libcal.com/passes"
SPL_RESERVE_BY_DATE_URL = "https://spl.libcal.com/admission"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"

PROVIDERS: dict[str, dict[str, str]] = {
    "kcls": {
        "passes_url": KCLS_RESERVE_BY_LOCATION_URL,
        "admission_url": KCLS_RESERVE_BY_DATE_URL,
        "book_url_pattern": r"rooms\.kcls\.org/.*/book",
        "artifact_prefix": "kcls",
    },
    "spl": {
        "passes_url": SPL_RESERVE_BY_LOCATION_URL,
        "admission_url": SPL_RESERVE_BY_DATE_URL,
        "book_url_pattern": r"spl\.libcal\.com/.*/book",
        "artifact_prefix": "spl",
    },
}


def provider_settings(provider: str) -> dict[str, str]:
    key = provider.casefold()
    if key not in PROVIDERS:
        raise ValueError(f"Unsupported library provider: {provider}")
    return PROVIDERS[key]


@dataclass
class BookingRequest:
    pass_info: dict[str, Any]
    target_date: date


@dataclass
class LibraryAccount:
    card_number: str
    pin: str
    email: str = ""


class PassCardParser(HTMLParser):
    def __init__(self, provider: str = "kcls", passes_url: str = KCLS_RESERVE_BY_LOCATION_URL) -> None:
        super().__init__()
        self.provider = provider
        self.passes_url = passes_url
        self.passes: list[dict[str, str]] = []
        self._in_card = False
        self._card_depth = 0
        self._in_title = False
        self._current: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "").split()

        if tag == "div" and "s-lc-passcard" in classes and not self._in_card:
            self._in_card = True
            self._card_depth = 1
            self._current = {}
            return

        if self._in_card and tag == "div":
            self._card_depth += 1

        if not self._in_card:
            return

        if tag == "h2" and "s-lc-eventcard-title" in classes:
            self._in_title = True
        elif tag == "a" and attr.get("href", "").startswith("/passes/"):
            self._current.setdefault("url", urljoin(self.passes_url, attr["href"]))
            self._current.setdefault("id", attr["href"].rstrip("/").split("/")[-1])
        elif tag == "img":
            if attr.get("src"):
                self._current.setdefault("image_url", attr["src"])
            if attr.get("alt"):
                self._current.setdefault("image_alt", attr["alt"])

    def handle_endtag(self, tag: str) -> None:
        if not self._in_card:
            return

        if tag == "h2":
            self._in_title = False
        elif tag == "div":
            self._card_depth -= 1
            if self._card_depth <= 0:
                if self._current.get("name") and self._current.get("url"):
                    self._current.setdefault("category", "museum")
                    self._current.setdefault("provider", self.provider)
                    self.passes.append(self._current)
                self._in_card = False

    def handle_data(self, data: str) -> None:
        if not self._in_card:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._current["name"] = re.sub(r"\s+", " ", text)


class DateAvailabilityParser(HTMLParser):
    def __init__(self, admission_url: str = KCLS_RESERVE_BY_DATE_URL) -> None:
        super().__init__()
        self.admission_url = admission_url
        self.options: list[dict[str, str]] = []
        self._in_museum = False
        self._museum_depth = 0
        self._in_heading = False
        self._current: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "").split()

        if tag == "div" and "s-lc-pass-date-museum" in classes and not self._in_museum:
            self._in_museum = True
            self._museum_depth = 1
            self._current = {}
            return

        if self._in_museum and tag == "div":
            self._museum_depth += 1

        if not self._in_museum:
            return

        if tag == "h3" and "media-heading" in classes:
            self._in_heading = True
        elif tag == "a" and "/book" in attr.get("href", ""):
            self._current["booking_url"] = urljoin(self.admission_url, attr["href"])

    def handle_endtag(self, tag: str) -> None:
        if not self._in_museum:
            return

        if tag == "h3":
            self._in_heading = False
        elif tag == "div":
            self._museum_depth -= 1
            if self._museum_depth <= 0:
                if self._current.get("name") and self._current.get("booking_url"):
                    self.options.append(self._current)
                self._in_museum = False

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            text = data.strip()
            if text:
                self._current["name"] = re.sub(r"\s+", " ", text)


def _ensure_playwright_installed() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install with `python -m pip install -e .[automation]` and run `playwright install`."
        ) from exc


def _launch_browser(headless: bool = True):
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    return playwright, browser, context, page


def _visible_text(page: Any, pattern: str) -> bool:
    try:
        return page.get_by_text(re.compile(pattern, re.IGNORECASE)).first.is_visible(timeout=1500)
    except Exception:
        return False


def _click_first(page: Any, selectors: list[str], timeout: int = 2500) -> bool:
    for selector in selectors:
        try:
            page.locator(selector).first.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _fill_first(page: Any, selectors: list[str], value: str, timeout: int = 2500) -> bool:
    if not value:
        return False

    for selector in selectors:
        try:
            page.locator(selector).first.fill(value, timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _is_visible(page: Any, selector: str, timeout: int = 1000) -> bool:
    try:
        return page.locator(selector).first.is_visible(timeout=timeout)
    except Exception:
        return False


def _complete_auth_if_needed(page: Any, account: LibraryAccount, provider: str = "kcls") -> tuple[bool, str]:
    if not _is_visible(page, "#s-libapps-libauth-form") and not _is_visible(page, "#username"):
        return True, "No auth form detected"

    if not account.card_number or not account.pin:
        _capture_artifacts(page, f"{provider}-auth-missing-credentials")
        return False, f"Auth form detected, but credentials for {provider.upper()} are missing"

    page.fill("#username", account.card_number)
    page.fill("#password", account.pin)
    page.click("#s-libapps-login-button")
    try:
        page.wait_for_url(re.compile(provider_settings(provider)["book_url_pattern"]), timeout=30000)
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)

    if _is_visible(page, "#s-libapps-libauth-form") or _visible_text(page, "invalid|incorrect|not recognized|failed"):
        _capture_artifacts(page, f"{provider}-auth-failed")
        return False, f"{provider.upper()} library card/PIN authentication did not complete"

    return True, "Library card/PIN authentication completed"


def _accept_terms_if_needed(page: Any) -> tuple[bool, str]:
    if not _is_visible(page, "#terms_accept", timeout=1500):
        return True, "No terms acknowledgement required"

    page.click("#terms_accept")
    try:
        page.wait_for_selector("#btn-form-submit", state="visible", timeout=10000)
    except Exception as exc:
        _capture_artifacts(page, "terms-accept-failed")
        return False, f"Terms were accepted, but the reservation form did not appear: {exc}"

    return True, "Terms acknowledged"


def _fill_required_email_if_needed(page: Any, account: LibraryAccount, artifact_prefix: str) -> tuple[bool, str]:
    if not _is_visible(page, "input[type='email']", timeout=1000):
        return True, "No email field detected"

    if not account.email:
        _capture_artifacts(page, f"{artifact_prefix}-missing-email")
        return False, "Email is required on this booking form, but no email is configured for this provider"

    filled = _fill_first(
        page,
        [
            "input[type='email']",
            "input[name*='email' i]",
            "input[id*='email' i]",
        ],
        account.email,
    )
    if not filled:
        _capture_artifacts(page, f"{artifact_prefix}-email-fill-failed")
        return False, "Email is required on this booking form, but the email field could not be filled"

    return True, "Email filled"


def _select_option_by_label(page: Any, selectors: list[str], label: str, timeout: int = 2500) -> bool:
    if not label:
        return False

    for selector in selectors:
        locator = page.locator(selector).first
        for kwargs in ({"label": label}, {"value": label}):
            try:
                locator.select_option(timeout=timeout, **kwargs)
                return True
            except Exception:
                continue
    return False


def _click_text(page: Any, text: str, timeout: int = 2500) -> bool:
    if not text:
        return False
    try:
        page.get_by_text(text, exact=False).first.click(timeout=timeout)
        return True
    except Exception:
        return False


def _date_variants(target_date: date) -> list[str]:
    return [
        target_date.isoformat(),
        target_date.strftime("%-m/%-d/%Y"),
        target_date.strftime("%m/%d/%Y"),
        target_date.strftime("%B %-d, %Y"),
        target_date.strftime("%b %-d, %Y"),
        str(target_date.day),
    ]


def _capture_artifacts(page: Any, prefix: str) -> dict[str, Path]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    html_path = ARTIFACTS_DIR / f"{prefix}.html"
    screenshot_path = ARTIFACTS_DIR / f"{prefix}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(screenshot_path), full_page=True)
    return {"html": html_path, "screenshot": screenshot_path}


def _goto(page: Any, url: str, selector: str | None = None) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if selector:
        page.wait_for_selector(selector, timeout=15000)


def parse_pass_cards(html: str, provider: str = "kcls") -> list[dict[str, str]]:
    settings = provider_settings(provider)
    parser = PassCardParser(provider=provider.casefold(), passes_url=settings["passes_url"])
    parser.feed(html)
    return parser.passes


def parse_date_availability(html: str, provider: str = "kcls") -> list[dict[str, str]]:
    settings = provider_settings(provider)
    parser = DateAvailabilityParser(admission_url=settings["admission_url"])
    parser.feed(html)
    return parser.options


def fetch_live_passes(provider: str = "kcls", headless: bool = True) -> list[dict[str, str]]:
    _ensure_playwright_installed()
    settings = provider_settings(provider)

    playwright = browser = context = page = None
    try:
        playwright, browser, context, page = _launch_browser(headless=headless)
        _goto(page, settings["passes_url"], selector=".s-lc-passcard")
        _capture_artifacts(page, f"{settings['artifact_prefix']}-passes-by-location")
        return parse_pass_cards(page.content(), provider=provider)
    finally:
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()


def find_booking_url_for_date(page: Any, pass_info: dict[str, Any], target_date: date) -> str | None:
    provider = str(pass_info.get("provider", "kcls")).casefold()
    settings = provider_settings(provider)
    url = f"{settings['admission_url']}?date={target_date.isoformat()}"
    _goto(page, url, selector="#s-lc-pass-availability-content")
    _capture_artifacts(page, f"{settings['artifact_prefix']}-availability-{target_date.isoformat()}")

    pass_name = str(pass_info.get("name", "")).casefold()
    pass_id = str(pass_info.get("id", ""))
    for option in parse_date_availability(page.content(), provider=provider):
        booking_url = option.get("booking_url", "")
        if pass_id and f"/passes/{pass_id}/book" in booking_url:
            return booking_url
        if pass_name and option.get("name", "").casefold() == pass_name:
            return booking_url
    return None


def inspect_reservation_site(provider: str = "kcls", headless: bool = True) -> dict[str, Path]:
    """Open live reservation pages and save HTML/screenshots for selector work."""
    _ensure_playwright_installed()
    settings = provider_settings(provider)

    playwright = browser = context = page = None
    artifacts: dict[str, Path] = {}
    try:
        playwright, browser, context, page = _launch_browser(headless=headless)

        for slug, url in (
            (f"{settings['artifact_prefix']}-passes-by-location", settings["passes_url"]),
            (f"{settings['artifact_prefix']}-passes-by-date", settings["admission_url"]),
        ):
            _goto(page, url)
            artifacts.update({f"{slug}-{key}": value for key, value in _capture_artifacts(page, slug).items()})

        return artifacts
    finally:
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()


def book_pass_for_date(
    page: Any,
    request: BookingRequest,
    account: LibraryAccount,
    dry_run: bool = False,
) -> tuple[bool, str]:
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
        direct_url = request.pass_info.get("booking_url") or find_booking_url_for_date(page, request.pass_info, request.target_date)
        if not direct_url:
            return False, "No available booking link found for this pass/date"

        _goto(page, direct_url)
        provider = str(request.pass_info.get("provider", "kcls")).casefold()
        auth_success, auth_message = _complete_auth_if_needed(page, account, provider=provider)
        if not auth_success:
            return False, auth_message

        terms_success, terms_message = _accept_terms_if_needed(page)
        if not terms_success:
            return False, terms_message

        artifact_prefix = f"{provider}-{request.target_date}-{name}".replace(" ", "-").lower()
        email_success, email_message = _fill_required_email_if_needed(page, account, artifact_prefix)
        if not email_success:
            return False, email_message

        if not _is_visible(page, "#btn-form-submit", timeout=1500):
            pass_name = str(request.pass_info.get("name", ""))
            _select_option_by_label(page, ["select", "select[name*='pass' i]", "select[name*='location' i]"], pass_name)
            _click_text(page, pass_name)

            for date_text in _date_variants(request.target_date):
                if _click_text(page, date_text):
                    break
            _fill_first(
                page,
                [
                    "input[type='date']",
                    "input[name*='date' i]",
                    "input[placeholder*='date' i]",
                ],
                request.target_date.isoformat(),
            )

            _fill_first(
                page,
                [
                    "input[name*='card' i]",
                    "input[id*='card' i]",
                    "input[placeholder*='card' i]",
                    "input[name*='barcode' i]",
                ],
                account.card_number,
            )
            _fill_first(
                page,
                [
                    "input[name*='pin' i]",
                    "input[id*='pin' i]",
                    "input[placeholder*='pin' i]",
                    "input[type='password']",
                ],
                account.pin,
            )
            _fill_first(
                page,
                [
                    "input[type='email']",
                    "input[name*='email' i]",
                    "input[id*='email' i]",
                ],
                account.email,
            )

            email_success, email_message = _fill_required_email_if_needed(page, account, artifact_prefix)
            if not email_success:
                return False, email_message

        if _visible_text(page, "unavailable|closed|no passes|no availability"):
            _capture_artifacts(page, f"failed-{request.target_date}-{name}".replace(" ", "-").lower())
            return False, "Pass/date appears unavailable"

        allow_live_submit = os.environ.get("LIBRARY_ALLOW_LIVE_SUBMIT", "0") == "1"
        if not allow_live_submit:
            _capture_artifacts(page, f"ready-{request.target_date}-{name}".replace(" ", "-").lower())
            return False, "Stopped before final submit. Set LIBRARY_ALLOW_LIVE_SUBMIT=1 to allow live reservation submission."

        clicked = _click_first(page, ["#btn-form-submit"], timeout=5000)
        if not clicked:
            clicked = _click_first(
                page,
                [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:has-text('Reserve')",
                    "button:has-text('Submit')",
                    "button:has-text('Book')",
                    "a:has-text('Reserve')",
                ],
                timeout=5000,
            )
        if not clicked:
            _capture_artifacts(page, f"failed-{request.target_date}-{name}".replace(" ", "-").lower())
            return False, "Could not find a final reservation button"

        page.wait_for_load_state("networkidle", timeout=15000)
        _capture_artifacts(page, f"submitted-{request.target_date}-{name}".replace(" ", "-").lower())

        if _is_visible(page, "#s-lc-bform", timeout=1000) or _is_visible(page, "input[type='email']", timeout=1000):
            return False, "Submission did not leave the booking form; check required fields or validation errors"

        if _visible_text(page, "confirmed|confirmation|reserved|success"):
            return True, "Reservation confirmation was detected"

        return False, "Submission completed, but confirmation text was not detected"
    except Exception as exc:
        try:
            _capture_artifacts(page, f"error-{request.target_date}-{name}".replace(" ", "-").lower())
        except Exception:
            pass
        return False, f"Booking attempt failed: {exc}"


def attempt_bookings(
    account: LibraryAccount,
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

        results: List[Tuple[BookingRequest, AttemptResult]] = []
        for pass_info in passes:
            for target_date in dates:
                request = BookingRequest(pass_info=pass_info, target_date=target_date)
                success, message = book_pass_for_date(page, request, account=account, dry_run=False)
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
