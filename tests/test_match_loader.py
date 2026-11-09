"""Malformed enrichment must not invent completed matches or corrupt a COPY."""
import unittest
import csv
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from loader.load_data import EXTRA_COLUMNS, load_matches, parse_match_extras, parse_match_result, season_folder_to_name


class MatchParsingTests(unittest.TestCase):
    def row(self, **changes):
        return dict(Date="02/02/2025", FTHG="0", FTAG="0", FTR="D", **changes)

    def test_missing_extras_default_to_null(self):
        self.assertEqual(parse_match_extras(self.row()), (None,) * len(EXTRA_COLUMNS))

    def test_shots_cards_and_odds_are_parsed(self):
        extras = parse_match_extras(self.row(
            HS="14", AS="9", HST="6", AST="3", HC="5", AC="2", HY="1", AY="3",
            HR="1", AR="0", HTHG="0", HTAG="0",
            B365H="2.10", B365D="3.40", B365A="3.20",
            AHh="-0.5", B365AHH="1.95", B365AHA="1.90",
        ))
        self.assertEqual(extras, (14, 9, 6, 3, 5, 2, 1, 3, 1, 0, 0, 0, 2.10, 3.40, 3.20, -0.5, 1.95, 1.90))

    def test_malformed_extra_value_does_not_reject_the_match(self):
        extras = parse_match_extras(self.row(HS="not-a-number", B365H=""))
        self.assertIsNone(extras[0])
        self.assertIsNone(extras[EXTRA_COLUMNS.index("odds_home")])

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


class MatchReplacementTests(unittest.TestCase):
    def connection(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            ("I1", "Home", 1), ("I1", "Away", 2),
        ]
        return conn

    def write_matches(self, base, rows):
        directory = Path(base) / "I1"
        directory.mkdir()
        with (directory / "2425.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])
            writer.writeheader()
            writer.writerows(rows)

    def test_missing_optional_directory_clears_old_rows(self):
        conn = self.connection()
        with tempfile.TemporaryDirectory() as base, patch("loader.load_data.MATCHES_DIR", str(Path(base) / "missing")), \
                patch("loader.load_data.execute_values") as insert:
            self.assertEqual(load_matches(conn), 0)
        conn.cursor.return_value.__enter__.return_value.execute.assert_any_call("TRUNCATE TABLE match_results;")
        conn.commit.assert_called_once()
        insert.assert_not_called()

    def test_duplicate_fixture_is_imported_once(self):
        row = dict(Date="02/02/2025", HomeTeam="Home", AwayTeam="Away", FTHG="2", FTAG="1", FTR="H")
        conn = self.connection()
        with tempfile.TemporaryDirectory() as base:
            self.write_matches(base, [row, row])
            with patch("loader.load_data.MATCHES_DIR", base), patch("loader.load_data.execute_values") as insert:
                self.assertEqual(load_matches(conn), 1)
        self.assertEqual(len(insert.call_args.args[2]), 1)

    def test_conflicting_fixture_preserves_stored_matches(self):
        row = dict(Date="02/02/2025", HomeTeam="Home", AwayTeam="Away", FTHG="2", FTAG="1", FTR="H")
        conn = self.connection()
        with tempfile.TemporaryDirectory() as base:
            self.write_matches(base, [row, dict(row, FTHG="3")])
            with patch("loader.load_data.MATCHES_DIR", base), self.assertRaisesRegex(ValueError, "Conflicting scores"):
                load_matches(conn)
        statements = [call.args[0] for call in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]
        self.assertNotIn("TRUNCATE TABLE match_results;", statements)
        conn.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
