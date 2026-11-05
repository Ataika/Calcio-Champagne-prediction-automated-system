"""A partially completed pipeline must not make the application look ready."""
import json
import unittest
from unittest.mock import patch

from app.api import REQUIRED_OUTPUT_TABLES, health


class HealthTests(unittest.TestCase):
    def tables(self, missing=()):
        return [dict(name=name, available=name not in missing) for name in REQUIRED_OUTPUT_TABLES]

    def test_all_outputs_and_results_are_ready(self):
        with patch("app.api.read", side_effect=[self.tables(), [dict(available=True)]]), \
                patch("app.api.MODEL_PATH") as model:
            model.exists.return_value = True
            response = health()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), dict(ready=True, model_available=True,
                                                        missing_tables=[], has_results=True))

    def test_partial_pipeline_reports_missing_table_without_querying_results(self):
        with patch("app.api.read", return_value=self.tables(["lab_team_features"])) as read, \
                patch("app.api.MODEL_PATH") as model:
            model.exists.return_value = False
            response = health()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body)["missing_tables"], ["lab_team_features"])
        self.assertEqual(read.call_count, 1)

    def test_empty_results_are_not_ready(self):
        with patch("app.api.read", side_effect=[self.tables(), [dict(available=False)]]):
            response = health()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(json.loads(response.body)["has_results"])

    def test_model_availability_is_reported_separately(self):
        with patch("app.api.read", side_effect=[self.tables(), [dict(available=True)]]), \
                patch("app.api.MODEL_PATH") as model:
            model.exists.return_value = False
            response = health()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.body)["model_available"])


if __name__ == "__main__":
    unittest.main()
