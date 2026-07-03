import tempfile
import unittest
from pathlib import Path

from src.results import append_attempt, create_attempt_result, load_attempts


class AttemptResultTests(unittest.TestCase):
    def test_append_and_load_attempts_newest_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results.jsonl"
            older = create_attempt_result(
                pass_info={"name": "Museum", "category": "museum"},
                target_date="2026-07-17",
                success=True,
                dry_run=True,
                message="First",
            )
            newer = create_attempt_result(
                pass_info={"name": "Zoo", "category": "zoo"},
                target_date="2026-07-18",
                success=False,
                dry_run=False,
                message="Second",
            )
            newer.attempted_at = "2026-07-03T12:00:01"
            older.attempted_at = "2026-07-03T12:00:00"

            append_attempt(older, path=path)
            append_attempt(newer, path=path)

            attempts = load_attempts(path=path)

            self.assertEqual([item.pass_name for item in attempts], ["Zoo", "Museum"])
            self.assertEqual(attempts[0].message, "Second")


if __name__ == "__main__":
    unittest.main()
