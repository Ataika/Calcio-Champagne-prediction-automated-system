"""Live API and data-contract checks. Run after docker compose up.

Uses only Python's standard library; does not mutate database data or train.
"""
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = os.getenv("CALCIO_URL", "http://localhost:8502")


def fetch(path, payload=None, expected=200):
    request = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={"Content-Type": "application/json"} if payload is not None else {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, content, headers = response.status, response.read().decode(), response.headers
    except urllib.error.HTTPError as error:
        status, content, headers = error.code, error.read().decode(), error.headers
    assert status == expected, (path, status, content[:300])
    assert headers.get("X-Content-Type-Options") == "nosniff"
    return json.loads(content) if headers.get("Content-Type", "").startswith("application/json") else content


def main():
    for attempt in range(20):
        try:
            assert fetch("/api/health")["ready"]
            break
        except (OSError, AssertionError):
            if attempt == 19:
                raise
            time.sleep(.25)
    meta = fetch("/api/meta")
    assert len(meta["leagues"]) == 5
    checks = ["ready output tables", "five-league metadata"]
    for league in meta["leagues"]:
        assert league["default_season"] == "24/25"
        season = fetch(f"/api/season?competition={league['id']}&season=24%2F25")
        assert len(season["rows"]) in (18, 20)
        assert all(row["matches"] >= 30 for row in season["rows"])
        assert len({row["team_id"] for row in season["rows"]}) == len(season["rows"])
        assert season["position_correlation"]["n"] == len(season["rows"])
        analysis = fetch(f"/api/analysis?competition={league['id']}&season=24%2F25")
        assert all(row["season_key"] < 2024 for row in analysis["rows"]), "Partial 25/26 must not be a target"
        assert len({(row["team_id"], row["season_name"]) for row in analysis["rows"]}) == len(analysis["rows"])
        checks.append(f"{league['id']}: unique complete season + consecutive target sample")
    chosen = fetch("/api/season?competition=IT1&season=24%2F25")["rows"][0]
    club = fetch(f"/api/clubs/{chosen['team_id']}?competition=IT1&season=24%2F25")
    assert all(row["competition_id"] == "IT1" for row in club["history"])
    config = fetch(f"/api/lab/config?team_id={chosen['team_id']}&competition=IT1&season=24%2F25")
    assert not config["missing"]
    assert config["features"]["champagne_index"] == chosen["champagne_index"]
    result = fetch("/api/lab/predict", config["features"])
    assert isinstance(result["next_index"], (float, int))
    assert result["evaluation"]["split"] == "chronological season holdout"
    invalid = dict(config["features"], attacking_spend=config["features"]["total_spend"] + 1)
    fetch("/api/lab/predict", invalid, 422)
    fetch("/api/season?competition=IT1%27%3B%20DROP%20TABLE%20x&season=24%2F25", expected=422)
    fetch("/api/season?competition=IT1&season=24%2F27", expected=422)
    checks.extend(["club history keeps competition identity", "real five-feature prefill + inference", "invalid inputs rejected"])
    meetings = fetch("/api/head-to-head?team_a=46&team_b=5&competition=IT1&season=24%2F25")
    assert meetings["enrichment_available"] and len(meetings["matches"]) == 2
    assert [(m["home_team_id"], m["home_goals"], m["away_goals"])
            for m in meetings["matches"]] == [(46, 1, 2), (5, 1, 1)]
    inter, milan = meetings["teams"]
    assert (inter["goals_for"], inter["goals_against"], inter["wins"], inter["draws"], inter["points"]) == (2, 3, 0, 1, 1)
    assert (milan["goals_for"], milan["goals_against"], milan["wins"], milan["draws"], milan["points"]) == (3, 2, 1, 1, 4)
    reverse = fetch("/api/head-to-head?team_a=5&team_b=46&competition=IT1&season=24%2F25")
    assert reverse["teams"] == meetings["teams"][::-1]
    empty = fetch("/api/head-to-head?team_a=46&team_b=5&competition=IT1&season=20%2F21")
    assert not empty["enrichment_available"] and empty["matches"] == []
    assert empty["teams"][0]["goals_per_match"] is None
    fetch("/api/head-to-head?team_a=46&team_b=46&competition=IT1&season=24%2F25", expected=422)
    fetch("/api/head-to-head?team_a=46&team_b=46%27%20OR%201=1&competition=IT1&season=24%2F25", expected=422)
    fetch("/api/head-to-head?team_a=46&team_b=11&competition=IT1&season=24%2F25", expected=404)
    checks.extend(["head-to-head scores, home/away totals and reversed clubs",
                   "missing match enrichment is distinct from zero goals", "invalid head-to-head clubs rejected"])
    exported = list(csv.DictReader(io.StringIO(fetch("/api/export?competition=IT1&season=24%2F25"))))
    assert len(exported) == 20
    project = fetch("/api/project")
    assert project["course_source_verified"]
    assert project["position"]["n_observations"] == 388
    assert project["ml"]["evaluation"]["test_rows"] > 0
    checks.extend(["filtered CSV export", "corrected evaluation + verified course source"])
    assert "The data" in fetch("/api/docs")
    assert fetch("/api/openapi.json")["paths"]["/api/lab/predict"]["post"]
    checks.append("local API reference + OpenAPI schema")
    artifacts = Path(__file__).resolve().parents[1] / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "live-check.json").write_text(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(),
                                                          "checks": checks, "passed": len(checks)}, indent=2))
    print(f"Passed {len(checks)} live API/data checks")


if __name__ == "__main__":
    main()
