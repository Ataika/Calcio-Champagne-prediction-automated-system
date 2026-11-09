"""Head-to-head results must preserve home/away perspective and source coverage."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api import head_to_head, summarize_head_to_head


class HeadToHeadTests(unittest.TestCase):
    def test_scores_reverse_for_away_club_and_include_draws(self):
        matches = [
            dict(home_team_id=1, away_team_id=2, home_goals=2, away_goals=0),
            dict(home_team_id=2, away_team_id=1, home_goals=4, away_goals=1),
            dict(home_team_id=1, away_team_id=2, home_goals=1, away_goals=1),
        ]
        first = summarize_head_to_head(1, "First", matches)
        second = summarize_head_to_head(2, "Second", matches)
        self.assertEqual((first["wins"], first["draws"], first["losses"]), (1, 1, 1))
        self.assertEqual((first["goals_for"], first["goals_against"]), (4, 5))
        self.assertEqual((second["goals_for"], second["goals_against"]), (5, 4))
        self.assertEqual((first["goal_difference"], second["goal_difference"]), (-1, 1))
        self.assertEqual((first["clean_sheets"], second["clean_sheets"]), (1, 0))
        self.assertEqual(first["points"], 4)
        self.assertAlmostEqual(first["goals_per_match"], 4 / 3)

    def test_goalless_draw_is_a_completed_match(self):
        stats = summarize_head_to_head(1, "First", [
            dict(home_team_id=2, away_team_id=1, home_goals=0, away_goals=0),
        ])
        self.assertEqual((stats["matches"], stats["draws"], stats["points"]), (1, 1, 1))
        self.assertEqual((stats["goals_per_match"], stats["clean_sheets"]), (0, 1))

    def test_match_statistics_keep_home_away_perspective_and_coverage(self):
        stats = summarize_head_to_head(1, "First", [
            dict(home_team_id=1, away_team_id=2, home_goals=2, away_goals=0,
                 home_shots=12, away_shots=8, home_shots_on_target=5,
                 away_shots_on_target=2, home_corners=6, away_corners=3),
            dict(home_team_id=2, away_team_id=1, home_goals=1, away_goals=0,
                 home_shots=10, away_shots=7, home_shots_on_target=3,
                 away_shots_on_target=1, home_corners=4, away_corners=2),
            dict(home_team_id=1, away_team_id=2, home_goals=0, away_goals=0),
        ])
        self.assertEqual(stats["shots_on_target_matches"], 2)
        self.assertEqual(stats["shots_on_target_per_match"], 3.0)
        self.assertEqual(stats["shots_on_target_against_per_match"], 2.5)
        self.assertEqual(stats["corners_per_match"], 4.0)

    def test_endpoint_preserves_requested_club_order_and_bound_scope(self):
        clubs = [dict(team_id=1, team_name="First"), dict(team_id=2, team_name="Second")]
        matches = [dict(match_date="2025-01-01", home_team_id=1, away_team_id=2,
                        home_goals=3, away_goals=1)]
        with patch("app.api.read", side_effect=[clubs, matches]) as read:
            data = head_to_head(2, 1, "IT1", "24/25")
        self.assertEqual([team["team_id"] for team in data["teams"]], [2, 1])
        self.assertEqual(data["teams"][0]["goals_for"], 1)
        self.assertEqual(data["matches"][0]["home_team_name"], "First")
        self.assertTrue(data["enrichment_available"])
        self.assertEqual(read.call_args_list[1].args[1], ("I1", "24/25", [2, 1], [2, 1]))

    def test_three_club_comparison_summarizes_each_clubs_direct_meetings(self):
        clubs = [dict(team_id=i, team_name=f"Club {i}") for i in (1, 2, 3)]
        matches = [
            dict(match_date="2024-09-01", home_team_id=1, away_team_id=2, home_goals=2, away_goals=0),
            dict(match_date="2024-10-01", home_team_id=3, away_team_id=1, home_goals=1, away_goals=1),
            dict(match_date="2024-11-01", home_team_id=2, away_team_id=3, home_goals=0, away_goals=1),
        ]
        with patch("app.api.read", side_effect=[clubs, matches]) as read:
            data = head_to_head(1, 2, "IT1", "24/25", team_c=3)
        self.assertEqual([team["team_id"] for team in data["teams"]], [1, 2, 3])
        self.assertEqual([team["matches"] for team in data["teams"]], [2, 2, 2])
        self.assertEqual([team["goals_for"] for team in data["teams"]], [3, 0, 2])
        self.assertEqual(read.call_args_list[1].args[1], ("I1", "24/25", [1, 2, 3], [1, 2, 3]))

    def test_empty_meetings_distinguish_missing_enrichment(self):
        clubs = [dict(team_id=1, team_name="First"), dict(team_id=2, team_name="Second")]
        for available in (False, True):
            with self.subTest(available=available), patch("app.api.read", side_effect=[
                clubs, [], [{"available": available}],
            ]):
                data = head_to_head(1, 2, "IT1", "24/25")
            self.assertEqual(data["enrichment_available"], available)
            self.assertEqual(data["matches"], [])
            self.assertEqual(data["teams"][0]["matches"], 0)
            self.assertIsNone(data["teams"][0]["goals_per_match"])

    def test_same_club_and_invalid_scope_are_rejected_before_query(self):
        with patch("app.api.read") as read:
            for args in [(1, 1, "IT1", "24/25"), (1, 2, "IT1", "24/27"),
                         (1, 2, "IT1; DROP TABLE x", "24/25")]:
                with self.subTest(args=args), self.assertRaises(HTTPException) as caught:
                    head_to_head(*args)
                self.assertEqual(caught.exception.status_code, 422)
            read.assert_not_called()

    def test_club_outside_selected_season_is_not_compared(self):
        with patch("app.api.read", return_value=[dict(team_id=1, team_name="First")]), \
                self.assertRaises(HTTPException) as caught:
            head_to_head(1, 2, "IT1", "24/25")
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
