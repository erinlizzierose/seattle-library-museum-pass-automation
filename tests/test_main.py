import unittest
from datetime import datetime as dt, date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import contextlib

import src.main as main
from src.results import AttemptResult
from src.web_app import _next_priority


class ComputeTargetDatesTests(unittest.TestCase):
    @patch("src.main.datetime")
    def test_compute_target_dates_selects_exact_date(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 5, 27, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)

        selected = main.compute_target_dates(["2026-06-10", "2026-06-11"], 14)

        self.assertEqual(selected, [date(2026, 6, 10)])

    @patch("src.main.datetime")
    def test_compute_target_dates_returns_empty_when_no_match(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 5, 27, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)

        selected = main.compute_target_dates(["2026-06-11"], 14)

        self.assertEqual(selected, [])


class BookingPlanTests(unittest.TestCase):
    @patch("src.main.datetime")
    def test_build_booking_plan_uses_priority_order(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)
        passes = [
            {"name": "MOPOP", "provider": "kcls"},
            {"name": "Woodland Park Zoo", "provider": "kcls"},
        ]
        desired = [
            {"pass_name": "MOPOP", "date": "2026-07-20", "priority": 2},
            {"pass_name": "Woodland Park Zoo", "date": "2026-07-20", "priority": 1},
        ]

        plan = main.build_booking_plan(desired, passes, days_ahead=14)

        self.assertEqual([item[0]["name"] for item in plan], ["Woodland Park Zoo", "MOPOP"])

    @patch("src.main.datetime")
    def test_build_booking_plan_skips_non_target_dates(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)

        plan = main.build_booking_plan(
            [{"pass_name": "MOPOP", "date": "2026-07-21", "priority": 1}],
            [{"name": "MOPOP", "provider": "kcls"}],
            days_ahead=14,
        )

        self.assertEqual(plan, [])

    @patch("src.main.datetime")
    def test_build_booking_plan_includes_spl_provider(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)

        plan = main.build_booking_plan(
            [{"provider": "spl", "pass_name": "Museum of Flight", "date": "2026-07-20", "priority": 1}],
            [{"provider": "spl", "name": "Museum of Flight"}],
            days_ahead=14,
        )

        self.assertEqual(plan[0][0]["provider"], "spl")
        self.assertEqual(plan[0][0]["name"], "Museum of Flight")

    def test_merge_provider_passes_replaces_only_selected_provider(self):
        merged = main.merge_provider_passes(
            [
                {"provider": "kcls", "name": "MOPOP"},
                {"provider": "spl", "name": "Old SPL Pass"},
                {"name": "Legacy KCLS Pass"},
            ],
            [{"provider": "spl", "name": "New SPL Pass"}],
            provider="spl",
        )

        self.assertEqual([item["name"] for item in merged], ["MOPOP", "Legacy KCLS Pass", "New SPL Pass"])

    @patch("src.main.datetime")
    def test_build_booking_plan_for_config_uses_provider_windows(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)
        config = SimpleNamespace(
            scheduler=SimpleNamespace(days_ahead=14),
            schedules={
                "kcls": SimpleNamespace(days_ahead=14),
                "spl": SimpleNamespace(days_ahead=30),
            },
        )

        plan = main.build_booking_plan_for_config(
            [
                {"provider": "kcls", "pass_name": "MOPOP", "date": "2026-07-20", "priority": 1},
                {"provider": "spl", "pass_name": "Museum of Flight", "date": "2026-08-05", "priority": 1},
            ],
            [
                {"provider": "kcls", "name": "MOPOP"},
                {"provider": "spl", "name": "Museum of Flight"},
            ],
            config,
        )

        self.assertEqual([(item[0]["provider"], item[1]) for item in plan], [("kcls", date(2026, 7, 20)), ("spl", date(2026, 8, 5))])

    @patch("src.main.datetime")
    def test_build_booking_plan_for_config_preserves_priority_order(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)
        config = SimpleNamespace(
            scheduler=SimpleNamespace(days_ahead=14),
            schedules={"kcls": SimpleNamespace(days_ahead=14)},
        )

        plan = main.build_booking_plan_for_config(
            [
                {"provider": "kcls", "pass_name": "MOPOP", "date": "2026-07-20", "priority": 3},
                {"provider": "kcls", "pass_name": "Woodland Park Zoo", "date": "2026-07-20", "priority": 1},
                {"provider": "kcls", "pass_name": "Seattle Aquarium", "date": "2026-07-20", "priority": 2},
            ],
            [
                {"provider": "kcls", "name": "MOPOP"},
                {"provider": "kcls", "name": "Woodland Park Zoo"},
                {"provider": "kcls", "name": "Seattle Aquarium"},
            ],
            config,
            provider="kcls",
        )

        self.assertEqual([item[0]["name"] for item in plan], ["Woodland Park Zoo", "Seattle Aquarium", "MOPOP"])

    def test_next_priority_is_scoped_to_provider_and_date(self):
        self.assertEqual(
            _next_priority(
                [
                    {"provider": "kcls", "date": "2026-07-20", "priority": 1},
                    {"provider": "kcls", "date": "2026-07-20", "priority": 2},
                    {"provider": "spl", "date": "2026-07-20", "priority": 1},
                    {"provider": "kcls", "date": "2026-07-21", "priority": 1},
                ],
                "kcls",
                "2026-07-20",
            ),
            3,
        )

    @patch("src.main.notify_attempt_summary")
    @patch("src.main.load_attempts")
    @patch("src.main.load_passes")
    @patch("src.main.load_desired_bookings")
    @patch("src.main.attempt_bookings")
    @patch("src.main.datetime")
    def test_run_once_stops_after_success_for_visit_month(
        self,
        mock_datetime,
        mock_attempt_bookings,
        mock_load_desired_bookings,
        mock_load_passes,
        mock_load_attempts,
        mock_notify,
    ):
        mock_load_attempts.return_value = []
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)
        mock_load_passes.return_value = [{"name": "Woodland Park Zoo", "provider": "kcls"}, {"name": "MOPOP", "provider": "kcls"}]
        mock_load_desired_bookings.return_value = [
            {"pass_name": "Woodland Park Zoo", "date": "2026-07-20", "priority": 1},
            {"pass_name": "MOPOP", "date": "2026-07-20", "priority": 2},
        ]
        request = SimpleNamespace(pass_info={"name": "Woodland Park Zoo"}, target_date=date(2026, 7, 20))
        result = SimpleNamespace(success=True, message="Reserved")
        mock_attempt_bookings.return_value = [(request, result)]
        config = SimpleNamespace(
            scheduler=SimpleNamespace(days_ahead=14),
            account=SimpleNamespace(card_number="card", pin="pin", email="email@example.com"),
            accounts={"kcls": SimpleNamespace(card_number="card", pin="pin", email="email@example.com")},
        )

        with contextlib.redirect_stdout(StringIO()):
            main.run_once(config)

        self.assertEqual(mock_attempt_bookings.call_count, 1)
        mock_notify.assert_called_once()


def make_attempt(**overrides) -> AttemptResult:
    fields = {
        "pass_name": "Woodland Park Zoo",
        "target_date": "2026-07-20",
        "success": True,
        "dry_run": False,
        "attempted_at": "2026-07-06T14:00:00",
        "message": "Reserved",
        "category": "museum",
        "provider": "kcls",
    }
    fields.update(overrides)
    return AttemptResult(**fields)


class BookedMonthsTests(unittest.TestCase):
    @patch("src.main.load_attempts")
    def test_only_successful_live_attempts_count(self, mock_load_attempts):
        mock_load_attempts.return_value = [
            make_attempt(),
            make_attempt(target_date="2026-08-05", success=False),
            make_attempt(target_date="2026-09-05", dry_run=True),
        ]

        self.assertEqual(main.load_booked_months(), {"kcls:2026-07"})

    @patch("src.main.load_attempts")
    def test_months_are_scoped_by_provider(self, mock_load_attempts):
        mock_load_attempts.return_value = [
            make_attempt(provider="kcls"),
            make_attempt(provider="spl"),
        ]

        self.assertEqual(main.load_booked_months(), {"kcls:2026-07", "spl:2026-07"})

    @patch("src.main.load_attempts")
    def test_legacy_rows_without_provider_default_to_kcls(self, mock_load_attempts):
        mock_load_attempts.return_value = [make_attempt(provider="")]

        self.assertEqual(main.load_booked_months(), {"kcls:2026-07"})

    @patch("src.main.load_attempts")
    def test_malformed_target_date_is_skipped_not_fatal(self, mock_load_attempts):
        mock_load_attempts.return_value = [
            make_attempt(target_date="not-a-date"),
            make_attempt(target_date="2026-07-20"),
        ]

        self.assertEqual(main.load_booked_months(), {"kcls:2026-07"})

    @patch("src.main.load_attempts")
    def test_unreadable_history_returns_empty_instead_of_raising(self, mock_load_attempts):
        mock_load_attempts.side_effect = ValueError("corrupt history line")

        with contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main.load_booked_months(), set())

    @patch("src.main.notify_attempt_summary")
    @patch("src.main.load_attempts")
    @patch("src.main.load_passes")
    @patch("src.main.load_desired_bookings")
    @patch("src.main.attempt_bookings")
    @patch("src.main.datetime")
    def test_run_once_skips_month_already_booked_on_an_earlier_day(
        self,
        mock_datetime,
        mock_attempt_bookings,
        mock_load_desired_bookings,
        mock_load_passes,
        mock_load_attempts,
        mock_notify,
    ):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)
        mock_load_passes.return_value = [{"name": "Woodland Park Zoo", "provider": "kcls"}]
        mock_load_desired_bookings.return_value = [
            {"pass_name": "Woodland Park Zoo", "date": "2026-07-20", "priority": 1},
        ]
        # A different pass for the same provider and visit month was booked weeks earlier.
        mock_load_attempts.return_value = [make_attempt(pass_name="MOPOP", target_date="2026-07-05")]
        config = SimpleNamespace(
            scheduler=SimpleNamespace(days_ahead=14),
            account=SimpleNamespace(card_number="card", pin="pin", email="email@example.com"),
            accounts={"kcls": SimpleNamespace(card_number="card", pin="pin", email="email@example.com")},
        )

        with contextlib.redirect_stdout(StringIO()):
            main.run_once(config)

        mock_attempt_bookings.assert_not_called()


class SchedulerResilienceTests(unittest.TestCase):
    class StopLoop(Exception):
        """Breaks out of run_scheduler's infinite loop from the sleep call."""

    @patch("src.main.time.sleep")
    @patch("src.main.scheduler_sleep_seconds")
    @patch("src.main.run_once")
    @patch("src.main.datetime")
    def test_scheduler_continues_after_run_once_raises(
        self, mock_datetime, mock_run_once, mock_sleep_seconds, mock_sleep
    ):
        mock_datetime.now.return_value = dt(2026, 8, 7, 14, 0, 30)
        mock_datetime.combine.side_effect = dt.combine
        mock_datetime.strptime.side_effect = dt.strptime
        mock_run_once.side_effect = RuntimeError("playwright failed to launch")
        mock_sleep_seconds.return_value = 0
        mock_sleep.side_effect = self.StopLoop()
        config = SimpleNamespace(
            scheduler=SimpleNamespace(run_time="14:00"),
            schedules={"kcls": SimpleNamespace(run_time="14:00")},
        )

        # Reaching the sleep call proves the RuntimeError did not escape the loop.
        with contextlib.redirect_stdout(StringIO()):
            with self.assertRaises(self.StopLoop):
                main.run_scheduler(config, provider="kcls")

        mock_run_once.assert_called_once()

    @patch("src.main.time.sleep")
    @patch("src.main.scheduler_sleep_seconds")
    @patch("src.main.run_once")
    @patch("src.main.datetime")
    def test_scheduler_survives_malformed_run_time(
        self, mock_datetime, mock_run_once, mock_sleep_seconds, mock_sleep
    ):
        mock_datetime.now.return_value = dt(2026, 8, 7, 14, 0, 30)
        mock_datetime.combine.side_effect = dt.combine
        mock_datetime.strptime.side_effect = dt.strptime
        mock_sleep_seconds.return_value = 0
        mock_sleep.side_effect = self.StopLoop()
        config = SimpleNamespace(
            scheduler=SimpleNamespace(run_time="not-a-time"),
            schedules={"kcls": SimpleNamespace(run_time="not-a-time")},
        )

        with contextlib.redirect_stdout(StringIO()):
            with self.assertRaises(self.StopLoop):
                main.run_scheduler(config, provider="kcls")

        mock_run_once.assert_not_called()


class SchedulerTimingTests(unittest.TestCase):
    def test_scheduler_sleep_uses_fast_polling_near_release(self):
        config = SimpleNamespace(
            scheduler=SimpleNamespace(run_time="14:00"),
            schedules={"kcls": SimpleNamespace(run_time="14:00")},
        )

        sleep_seconds = main.scheduler_sleep_seconds(config, ["kcls"], dt(2026, 8, 5, 13, 59, 30))

        self.assertEqual(sleep_seconds, 0.25)

    def test_scheduler_sleep_wakes_at_start_of_fast_window(self):
        config = SimpleNamespace(
            scheduler=SimpleNamespace(run_time="14:00"),
            schedules={"kcls": SimpleNamespace(run_time="14:00")},
        )

        sleep_seconds = main.scheduler_sleep_seconds(config, ["kcls"], dt(2026, 8, 5, 13, 58, 55))

        self.assertEqual(sleep_seconds, 5)

    def test_scheduler_sleep_uses_normal_polling_far_from_release(self):
        config = SimpleNamespace(
            scheduler=SimpleNamespace(run_time="14:00"),
            schedules={"kcls": SimpleNamespace(run_time="14:00")},
        )

        sleep_seconds = main.scheduler_sleep_seconds(config, ["kcls"], dt(2026, 8, 5, 13, 0, 0))

        self.assertEqual(sleep_seconds, 10)


if __name__ == "__main__":
    unittest.main()
