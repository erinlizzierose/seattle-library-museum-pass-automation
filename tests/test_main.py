import unittest
from datetime import datetime as dt, date
from unittest.mock import patch

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
            {"name": "MOPOP"},
            {"name": "Woodland Park Zoo"},
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
            [{"name": "MOPOP"}],
            days_ahead=14,
        )

        self.assertEqual(plan, [])


if __name__ == "__main__":
    unittest.main()
