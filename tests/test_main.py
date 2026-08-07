import unittest
from datetime import datetime as dt, date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import contextlib

import src.main as main
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
        mock_notify,
    ):
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
