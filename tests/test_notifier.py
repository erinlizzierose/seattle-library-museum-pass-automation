import ssl
import unittest
from unittest.mock import patch

from src.notifier import build_attempt_summary, email_is_configured, send_email, send_test_email, EmailConfig
from src.results import AttemptResult


class NotifierTests(unittest.TestCase):
    def test_build_attempt_summary_for_success(self):
        result = AttemptResult(
            pass_name="National Nordic Museum",
            target_date="2026-08-05",
            success=True,
            dry_run=False,
            attempted_at="2026-07-06T12:01:00",
            message="Reservation confirmation was detected",
            category="museum",
            provider="spl",
        )

        subject, body = build_attempt_summary("spl", [result])

        self.assertEqual(subject, "SPL pass booked: National Nordic Museum")
        self.assertIn("Visit date: 2026-08-05", body)
        self.assertIn("SUCCESS", body)

    def test_email_is_not_configured_without_recipient(self):
        config = EmailConfig(
            host="smtp.example.test",
            port=587,
            username="sender@example.test",
            password="secret",
            sender="sender@example.test",
            recipient="",
            enabled=True,
        )

        self.assertFalse(email_is_configured(config))

    @patch("src.notifier.smtplib.SMTP")
    def test_send_email_verifies_server_certificate(self, mock_smtp):
        config = EmailConfig(
            host="smtp.example.test",
            port=587,
            username="sender@example.test",
            password="secret",
            sender="sender@example.test",
            recipient="recipient@example.test",
            enabled=True,
        )

        self.assertTrue(send_email("subject", "body", config))

        smtp = mock_smtp.return_value.__enter__.return_value
        context = smtp.starttls.call_args.kwargs.get("context")
        self.assertIsNotNone(context, "starttls must be given an explicit SSL context")
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @patch("src.notifier.send_email")
    def test_send_test_email_uses_fixed_subject(self, mock_send_email):
        mock_send_email.return_value = True

        self.assertTrue(send_test_email())

        subject, body = mock_send_email.call_args.args
        self.assertEqual(subject, "Seattle Library Museum Passes Automation test email")
        self.assertIn("test notification", body)


if __name__ == "__main__":
    unittest.main()
