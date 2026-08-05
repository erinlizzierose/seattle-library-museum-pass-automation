import unittest
from datetime import date

from src.booker import parse_date_availability, parse_pass_calendar_day, parse_pass_cards


class KclsParsingTests(unittest.TestCase):
    def test_parse_pass_cards_extracts_live_pass_metadata(self):
        html = """
        <div class="s-lc-eventcard s-lc-passcard">
          <h2 class="s-lc-eventcard-title">
            <a href="/passes/abc123">Seattle Aquarium</a>
          </h2>
          <img src="https://example.test/aquarium.png" alt="Seattle Aquarium">
          <a href="/passes/abc123" class="btn s-lc-passcard-book-btn">Book Now</a>
        </div>
        """

        passes = parse_pass_cards(html)

        self.assertEqual(len(passes), 1)
        self.assertEqual(passes[0]["name"], "Seattle Aquarium")
        self.assertEqual(passes[0]["id"], "abc123")
        self.assertEqual(passes[0]["url"], "https://rooms.kcls.org/passes/abc123")
        self.assertEqual(passes[0]["provider"], "kcls")

    def test_parse_pass_cards_uses_spl_base_url(self):
        html = """
        <div class="s-lc-eventcard s-lc-passcard">
          <h2 class="s-lc-eventcard-title">
            <a href="/passes/Zoo">Woodland Park Zoo</a>
          </h2>
          <a href="/passes/Zoo" class="btn s-lc-passcard-book-btn">Book Now</a>
        </div>
        """

        passes = parse_pass_cards(html, provider="spl")

        self.assertEqual(passes[0]["provider"], "spl")
        self.assertEqual(passes[0]["id"], "Zoo")
        self.assertEqual(passes[0]["url"], "https://spl.libcal.com/passes/Zoo")

    def test_parse_date_availability_extracts_booking_url(self):
        html = """
        <div class="s-lc-pass-date-museum">
          <div class="media-body">
            <h3 class="media-heading">MOHAI</h3>
            <a href="/passes/dcb899890d0c/book?pass=02a6adf05e41&amp;date=2026-07-17">
              Book Digital Pass Now
            </a>
          </div>
        </div>
        """

        options = parse_date_availability(html)

        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["name"], "MOHAI")
        self.assertEqual(
            options[0]["booking_url"],
            "https://rooms.kcls.org/passes/dcb899890d0c/book?pass=02a6adf05e41&date=2026-07-17",
        )

    def test_parse_date_availability_uses_spl_base_url(self):
        html = """
        <div class="s-lc-pass-date-museum">
          <div class="media-body">
            <h3 class="media-heading">Woodland Park Zoo</h3>
            <a href="/passes/Zoo/book?pass=abc&amp;date=2026-07-17">
              Book Digital Pass Now
            </a>
          </div>
        </div>
        """

        options = parse_date_availability(html, provider="spl")

        self.assertEqual(
            options[0]["booking_url"],
            "https://spl.libcal.com/passes/Zoo/book?pass=abc&date=2026-07-17",
        )

    def test_parse_pass_calendar_day_extracts_unavailable_status(self):
        html = """
        <div class="day day-Wed day-2026-08-19">
          <div class="day-number">
            <span class="s-lc-pass-availability s-lc-pass-unavailable">19</span>
          </div>
        </div>
        """

        day = parse_pass_calendar_day(
            html,
            target_date=date(2026, 8, 19),
            pass_url="https://rooms.kcls.org/passes/8e456682901d",
        )

        self.assertEqual(day, {"status": "unavailable"})

    def test_parse_pass_calendar_day_extracts_booking_url(self):
        html = """
        <div class="day day-Wed day-2026-08-19">
          <div class="day-number">
            <a class="s-lc-pass-availability s-lc-pass-available" href="/passes/8e456682901d/book?pass=abc&amp;date=2026-08-19">19</a>
          </div>
        </div>
        """

        day = parse_pass_calendar_day(
            html,
            target_date=date(2026, 8, 19),
            pass_url="https://rooms.kcls.org/passes/8e456682901d",
        )

        self.assertEqual(day["status"], "available")
        self.assertEqual(
            day["booking_url"],
            "https://rooms.kcls.org/passes/8e456682901d/book?pass=abc&date=2026-08-19",
        )


if __name__ == "__main__":
    unittest.main()
