"""Regression tests for audit findings. Run in the app image with source mounted.

docker compose run --rm --no-deps -v "$PWD:/source:ro" -w /source app \
    python -m unittest discover -s tests -v
"""
import csv
import io
import math
import pathlib
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import Scenario, clean, regression, scope
from loader.get_data import validate
from pipeline.compute_predictions import build_ml_features, compute, fit_ml_model, season_sort_key


class TargetTests(unittest.TestCase):
    def test_missing_year_is_not_next_season(self):
        rows = pd.DataFrame([
            dict(team_id=1, team_name="Club", competition_id="IT1", competition_name="Serie A", season_name="21/22", matches=38, champagne_index=2, total_goals=60, total_assists=16, total_goals_conceded=40, total_clean_sheets=10, goals_conceded_per_match=1.05, clean_sheet_rate=0.26),
            dict(team_id=1, team_name="Club", competition_id="IT1", competition_name="Serie A", season_name="23/24", matches=38, champagne_index=3, total_goals=90, total_assists=24, total_goals_conceded=35, total_clean_sheets=12, goals_conceded_per_match=0.92, clean_sheet_rate=0.32),
            dict(team_id=1, team_name="Club", competition_id="IT1", competition_name="Serie A", season_name="24/25", matches=38, champagne_index=4, total_goals=120, total_assists=32, total_goals_conceded=30, total_clean_sheets=14, goals_conceded_per_match=0.79, clean_sheet_rate=0.37),
            dict(team_id=1, team_name="Club", competition_id="IT1", competition_name="Serie A", season_name="25/26", matches=3, champagne_index=6, total_goals=12, total_assists=6, total_goals_conceded=2, total_clean_sheets=1, goals_conceded_per_match=0.67, clean_sheet_rate=0.33),
        ])
        spend = pd.DataFrame([
            dict(team_id=1, season_name=s, total_spend=1e6, attacking_spend=0, midfield_spend=0,
                 defensive_spend=0, goalkeeper_spend=0, total_sales=0, net_spend=1e6)
            for s in rows.season_name
        ])
        with patch("pipeline.compute_predictions.pd.read_sql", side_effect=[rows, spend]):
            result, _, _ = compute(None, set())
        targets = result.set_index("season_name").delta_index
        self.assertTrue(pd.isna(targets["21/22"]))
        self.assertEqual(targets["23/24"], 1)
        self.assertTrue(pd.isna(targets["24/25"]))
        self.assertTrue(pd.isna(targets["25/26"]))

    def test_market_lag_is_shared_across_competitions(self):
        merged = pd.DataFrame([dict(team_id=1, season_name=s, season_key=y, competition_id=c) for s,y in [("23/24",2023),("24/25",2024)] for c in ["IT1","CL"]])
        roster = pd.DataFrame([dict(team_id=1, season_name=s, player_id=p) for s in ["23/24","24/25"] for p in [1,2]])
        profiles = pd.DataFrame([dict(player_id=1,birth_year=2000),dict(player_id=2,birth_year=1990)])
        values = pd.DataFrame([dict(player_id=p,season_key=y,value=v) for p,y,v in [(1,2023,1e6),(2,2023,3e6),(1,2024,2e6),(2,2024,4e6)]])
        with patch("pipeline.compute_predictions.pd.read_sql", side_effect=[roster,profiles,values]):
            result = build_ml_features(None, merged)
        self.assertEqual(result[result.season_key==2024].market_value_change.tolist(), [1e6,1e6])
        self.assertTrue(result[result.season_key==2023].market_value_change.isna().all())
        self.assertEqual(len(result), len(merged))

    def test_temporal_evaluation_has_baseline_and_counts(self):
        frame=pd.DataFrame([dict(team_id=team, season_key=year, matches=38,
             champagne_index=2+team/40,total_spend=1e6*team,attacking_spend=1e5*team,
             squad_avg_age=24+team/10,market_value_change=year*1000,delta_index=.2*math.sin(team+year))
             for year in range(2010,2024) for team in range(1,21)])
        result=fit_ml_model(frame,{20})
        self.assertIsNotNone(result)
        evaluation=result[5]
        cutoff=evaluation["test_from_season"]
        eligible=frame[frame.team_id!=20]
        self.assertEqual(evaluation["train_rows"],int((eligible.season_key<cutoff).sum()))
        self.assertEqual(evaluation["test_rows"],int((eligible.season_key>=cutoff).sum()))
        self.assertGreater(evaluation["baseline_mae"],0)
        self.assertTrue(math.isfinite(evaluation["mae"]))

    def test_century_boundary(self):
        self.assertEqual(season_sort_key("99/00"),1999)
        self.assertEqual(season_sort_key("24/25"),2024)
        self.assertIsNone(season_sort_key("not-a-season"))


class APITests(unittest.TestCase):
    def inputs(self, **extra):
        return dict(champagne_index=3,total_spend=20e6,attacking_spend=5e6,
                    squad_avg_age=25,market_value_change=1e6,**extra)

    def test_attack_budget_and_non_finite_values_rejected(self):
        values=self.inputs();values["attacking_spend"]=values["total_spend"]+1
        with self.assertRaises(ValidationError):Scenario(**values)
        values=self.inputs();values["champagne_index"]=float("nan")
        with self.assertRaises(ValidationError):Scenario(**values)
        values=self.inputs();values["market_value_change"]=float("inf")
        with self.assertRaises(ValidationError):Scenario(**values)

    def test_valid_zero_budget(self):
        values=self.inputs();values.update(total_spend=0,attacking_spend=0)
        self.assertEqual(Scenario(**values).total_spend,0)

    def test_scope_rejects_injection_and_nonconsecutive_years(self):
        scope("IT1","24/25")
        for comp,season in [("IT1; DROP TABLE x","24/25"),("IT1","24/27"),("IT1","2024"),("GB1","24/25' OR 1=1")]:
            with self.assertRaises(HTTPException):scope(comp,season)

    def test_json_replaces_missing_and_infinite_numbers(self):
        self.assertEqual(clean({"a":Decimal("3.5"),"b":[float("nan"),float("inf")]}),{"a":3.5,"b":[None,None]})

    def test_degenerate_chart_samples_have_no_fictitious_correlation(self):
        result=regression([{"x":1,"y":2}]*5,"x","y")
        self.assertIsNone(result["r"])
        self.assertEqual(result["n"],5)


class SourceTests(unittest.TestCase):
    def test_wrong_column_order_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/"sample.csv"
            path.write_text("second,first\n2,1\n")
            with self.assertRaises(ValueError):validate(path,{"header":["first","second"]})

    def test_goalkeeper_conceded_rate_keeps_fractional_goals(self):
        query = (pathlib.Path(__file__).resolve().parents[1] / "sql/champagne_queries.sql").read_text()
        self.assertIn("SUM(goals_conceded)::numeric / NULLIF(MAX(nb_in_group), 0)", query)


if __name__ == "__main__":
    unittest.main()
