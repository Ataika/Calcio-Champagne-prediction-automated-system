"""Verification must accept a fresh primary-data setup without optional match CSVs."""
import copy
import unittest

from scripts.check_live import check_head_to_head


class LiveContractTests(unittest.TestCase):
    def empty_sample(self, available):
        return dict(enrichment_available=available, matches=[], teams=[
            dict(team_id=team, matches=0, wins=0, draws=0, losses=0,
                 goals_for=0, goals_against=0, goal_difference=0, goals_per_match=None, points=0)
            for team in (1, 2)
        ])

    def test_no_optional_match_source_is_a_valid_contract(self):
        check_head_to_head(self.empty_sample(False), 1, 2)

    def test_no_meetings_in_present_source_is_a_valid_contract(self):
        check_head_to_head(self.empty_sample(True), 1, 2)

    def test_empty_sample_must_not_invent_a_goal_rate(self):
        data = self.empty_sample(False)
        data["teams"][0]["goals_per_match"] = 0
        with self.assertRaises(AssertionError):
            check_head_to_head(data, 1, 2)

    def test_inconsistent_goals_are_detected(self):
        data = self.empty_sample(True)
        first = data["teams"][0]
        second = data["teams"][1]
        first.update(matches=1, wins=1, goals_for=2, goal_difference=2, goals_per_match=2, points=3)
        second.update(matches=1, losses=1, goals_against=2, goal_difference=-2, goals_per_match=0)
        data["matches"] = [dict(home_team_id=1, away_team_id=2, home_goals=2, away_goals=0)]
        check_head_to_head(data, 1, 2)
        wrong = copy.deepcopy(data)
        wrong["matches"][0]["home_goals"] = 3
        with self.assertRaises(AssertionError):
            check_head_to_head(wrong, 1, 2)


if __name__ == "__main__":
    unittest.main()
