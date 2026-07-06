import unittest
from datetime import datetime as dt, date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import contextlib

import src.main as main


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
    def test_build_booking_plan_skips_unimplemented_provider(self, mock_datetime):
        mock_datetime.now.return_value = dt(2026, 7, 6, 10, 0, 0)
        mock_datetime.fromisoformat.side_effect = lambda s: dt.fromisoformat(s)

        with contextlib.redirect_stdout(StringIO()):
            plan = main.build_booking_plan(
                [{"provider": "spl", "pass_name": "Museum of Flight", "date": "2026-07-20", "priority": 1}],
                [{"provider": "kcls", "name": "Museum of Flight"}],
                days_ahead=14,
            )

        self.assertEqual(plan, [])

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
        )

        with contextlib.redirect_stdout(StringIO()):
            main.run_once(config)

        self.assertEqual(mock_attempt_bookings.call_count, 1)


if __name__ == "__main__":
    unittest.main()
