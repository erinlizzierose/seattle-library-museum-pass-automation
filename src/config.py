import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
CONFIG_PATH = BASE_DIR / "config.yaml"
PASSES_PATH = BASE_DIR / "data" / "passes.json"
DATES_PATH = BASE_DIR / "data" / "dates.json"
DESIRED_BOOKINGS_PATH = BASE_DIR / "data" / "desired_bookings.json"


@dataclass
class SchedulerConfig:
    run_time: str
    days_ahead: int
    timezone: str


@dataclass
class LibraryAccountConfig:
    card_number: str
    pin: str
    email: str


@dataclass
class AppConfig:
    account: LibraryAccountConfig
    accounts: dict[str, LibraryAccountConfig]
    scheduler: SchedulerConfig
    schedules: dict[str, SchedulerConfig]


def _account_from_env(provider: str, fallback_to_legacy: bool = False) -> LibraryAccountConfig:
    prefix = f"{provider.upper()}_LIBRARY"
    legacy_card = os.environ.get("LIBRARY_CARD_NUMBER", os.environ.get("LIBRARY_USERNAME", ""))
    legacy_pin = os.environ.get("LIBRARY_PIN", os.environ.get("LIBRARY_PASSWORD", ""))
    legacy_email = os.environ.get("LIBRARY_EMAIL", "")

    return LibraryAccountConfig(
        card_number=os.environ.get(f"{prefix}_CARD_NUMBER", legacy_card if fallback_to_legacy else ""),
        pin=os.environ.get(f"{prefix}_PIN", legacy_pin if fallback_to_legacy else ""),
        email=os.environ.get(f"{prefix}_EMAIL", legacy_email if fallback_to_legacy else ""),
    )


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> AppConfig:
    raw = load_yaml(CONFIG_PATH)
    scheduler = raw.get("scheduler", {})
    provider_schedules = scheduler.get("providers", {})

    kcls_account = _account_from_env("kcls", fallback_to_legacy=True)
    spl_account = _account_from_env("spl")
    legacy_schedule = SchedulerConfig(
        run_time=scheduler.get("run_time", "14:00"),
        days_ahead=int(scheduler.get("days_ahead", 14)),
        timezone=scheduler.get("timezone", "local"),
    )

    def schedule_for(provider: str, default_run_time: str, default_days_ahead: int) -> SchedulerConfig:
        raw_schedule = provider_schedules.get(provider, {})
        return SchedulerConfig(
            run_time=raw_schedule.get("run_time", default_run_time),
            days_ahead=int(raw_schedule.get("days_ahead", default_days_ahead)),
            timezone=raw_schedule.get("timezone", legacy_schedule.timezone),
        )

    return AppConfig(
        account=kcls_account,
        accounts={
            "kcls": kcls_account,
            "spl": spl_account,
        },
        scheduler=legacy_schedule,
        schedules={
            "kcls": schedule_for("kcls", legacy_schedule.run_time, legacy_schedule.days_ahead),
            "spl": schedule_for("spl", "12:00", 30),
        },
    )


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_passes() -> list[dict[str, Any]]:
    return load_json(PASSES_PATH)


def load_dates() -> list[str]:
    return load_json(DATES_PATH)


def load_desired_bookings() -> list[dict[str, Any]]:
    if not DESIRED_BOOKINGS_PATH.exists():
        return []
    return load_json(DESIRED_BOOKINGS_PATH)


def save_passes(passes: list[dict[str, Any]]) -> None:
    save_json(PASSES_PATH, passes)


def save_dates(dates: list[str]) -> None:
    unique_dates = sorted(set(dates))
    save_json(DATES_PATH, unique_dates)


def save_desired_bookings(bookings: list[dict[str, Any]]) -> None:
    normalized = sorted(
        ({**item, "provider": item.get("provider", "kcls")} for item in bookings),
        key=lambda item: (
            item.get("provider", "kcls"),
            item.get("date", ""),
            int(item.get("priority", 9999)),
            item.get("pass_name", ""),
        ),
    )
    save_json(DESIRED_BOOKINGS_PATH, normalized)
