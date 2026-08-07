import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from src.results import AttemptResult


@dataclass
class EmailConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str
    enabled: bool


def load_email_config() -> EmailConfig:
    username = os.environ.get("SMTP_USERNAME", "")
    sender = os.environ.get("SMTP_FROM", username)
    return EmailConfig(
        host=os.environ.get("SMTP_HOST", ""),
        port=int(os.environ.get("SMTP_PORT", "587")),
        username=username,
        password=os.environ.get("SMTP_PASSWORD", ""),
        sender=sender,
        recipient=os.environ.get("NOTIFY_EMAIL_TO", ""),
        enabled=os.environ.get("NOTIFY_EMAIL_ENABLED", "1") == "1",
    )


def email_is_configured(config: EmailConfig) -> bool:
    return bool(config.enabled and config.host and config.sender and config.recipient)


def _field(result: AttemptResult, name: str, default: str = "") -> str:
    return str(getattr(result, name, default))


def build_attempt_summary(provider: str, results: list[AttemptResult]) -> tuple[str, str]:
    provider_label = provider.upper()
    successes = [item for item in results if item.success]
    live_results = [item for item in results if not getattr(item, "dry_run", False)]

    if successes:
        first = successes[0]
        subject = f"{provider_label} pass booked: {_field(first, 'pass_name', '<unknown pass>')}"
        body = [
            f"{provider_label} pass booked",
            "",
            f"Pass: {_field(first, 'pass_name', '<unknown pass>')}",
            f"Visit date: {_field(first, 'target_date')}",
            f"Attempted at: {_field(first, 'attempted_at')}",
            "",
            "Attempt details:",
        ]
    else:
        subject = f"{provider_label} booking attempt failed"
        body = [
            f"{provider_label} booking attempt failed",
            "",
            "No pass was booked.",
            "",
            "Attempt details:",
        ]

    for item in live_results or results:
        status = "SUCCESS" if item.success else "FAILED"
        body.append(
            f"- {_field(item, 'target_date')}: {_field(item, 'pass_name', '<unknown pass>')}: {status} - {_field(item, 'message')}"
        )

    return subject, "\n".join(body)


def send_email(subject: str, body: str, config: EmailConfig | None = None) -> bool:
    config = config or load_email_config()
    if not email_is_configured(config):
        print("Email notifications are not configured; skipping notification.")
        return False

    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = config.recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(config.host, config.port, timeout=20) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if config.username and config.password:
            smtp.login(config.username, config.password)
        smtp.send_message(message)

    return True


def send_test_email() -> bool:
    return send_email(
        "Seattle Library Museum Passes Automation test email",
        "This is a test notification from Seattle Library Museum Passes Automation.",
    )


def notify_attempt_summary(provider: str, results: list[AttemptResult]) -> bool:
    live_results = [item for item in results if not getattr(item, "dry_run", False)]
    if not live_results:
        return False

    subject, body = build_attempt_summary(provider, live_results)
    try:
        return send_email(subject, body)
    except Exception as exc:
        print(f"Email notification failed: {exc}")
        return False
