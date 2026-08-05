import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_PATH = BASE_DIR / "data" / "results.jsonl"


@dataclass
class AttemptResult:
    pass_name: str
    target_date: str
    success: bool
    dry_run: bool
    attempted_at: str
    message: str = ""
    category: str = ""
    provider: str = ""


def create_attempt_result(
    pass_info: dict[str, Any],
    target_date: Any,
    success: bool,
    dry_run: bool,
    message: str = "",
) -> AttemptResult:
    return AttemptResult(
        pass_name=str(pass_info.get("name", "<unnamed>")),
        category=str(pass_info.get("category", "")),
        provider=str(pass_info.get("provider", "kcls")),
        target_date=target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date),
        success=success,
        dry_run=dry_run,
        attempted_at=datetime.now().isoformat(timespec="seconds"),
        message=message,
    )


def append_attempt(result: AttemptResult, path: Path = RESULTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(result), sort_keys=True) + "\n")


def load_attempts(path: Path = RESULTS_PATH, limit: int | None = None) -> list[AttemptResult]:
    if not path.exists():
        return []

    attempts: list[AttemptResult] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            attempts.append(AttemptResult(**raw))

    attempts.sort(key=lambda item: item.attempted_at, reverse=True)
    if limit is not None:
        return attempts[:limit]
    return attempts
