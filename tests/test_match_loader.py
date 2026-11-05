"""Malformed enrichment must not invent completed matches or corrupt a COPY."""
import unittest
from datetime import date

from loader.load_data import parse_match_result, season_folder_to_name


class MatchParsingTests(unittest.TestCase):
    def row(self, **changes):
        return dict(Date="02/02/2025", FTHG="0", FTAG="0", FTR="D", **changes)

    def test_goalless_draw_and_both_date_formats(self):
        for stamp in ("02/02/2025", "02/02/25"):
            row = self.row()
            row["Date"] = stamp
            self.assertEqual(parse_match_result(row), (date(2025, 2, 2), 0, 0, "D"))

    def test_unplayed_fixture_is_not_a_goalless_draw(self):
        self.assertIsNone(parse_match_result(dict(Date="02/02/2025", FTHG="", FTAG="", FTR="")))

    def test_invalid_dates_scores_and_results_are_rejected(self):
        for changes in (dict(Date="31/02/2025"), dict(FTHG=""), dict(FTAG=None),
                        dict(FTHG="-1"), dict(FTHG="1.5"), dict(FTR="H"), dict(FTR="X")):
            row = self.row()
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_match_result(row)

    def test_filename_requires_consecutive_years(self):
        self.assertEqual(season_folder_to_name("2425"), "24/25")
        self.assertEqual(season_folder_to_name("9900"), "99/00")
        for filename in ("2025", "2427", "24-25", "notes", ""):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                season_folder_to_name(filename)


if __name__ == "__main__":
    unittest.main()
