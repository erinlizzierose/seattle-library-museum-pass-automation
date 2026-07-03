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


@dataclass
class SchedulerConfig:
    run_time: str
    days_ahead: int
    timezone: str


@dataclass
class LoginConfig:
    username: str
    password: str


@dataclass
class AppConfig:
    login: LoginConfig
    scheduler: SchedulerConfig


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> AppConfig:
    raw = load_yaml(CONFIG_PATH)
    scheduler = raw.get("scheduler", {})

    return AppConfig(
        login=LoginConfig(
            username=os.environ.get("LIBRARY_USERNAME", ""),
            password=os.environ.get("LIBRARY_PASSWORD", ""),
        ),
        scheduler=SchedulerConfig(
            run_time=scheduler.get("run_time", "14:00"),
            days_ahead=int(scheduler.get("days_ahead", 14)),
            timezone=scheduler.get("timezone", "local"),
        ),
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


def save_passes(passes: list[dict[str, Any]]) -> None:
    save_json(PASSES_PATH, passes)


def save_dates(dates: list[str]) -> None:
    unique_dates = sorted(set(dates))
    save_json(DATES_PATH, unique_dates)
