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


if __name__ == "__main__":
    unittest.main()
