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


def check_head_to_head(data, team_a, team_b):
    first, second = data["teams"]
    assert [first["team_id"], second["team_id"]] == [team_a, team_b]
    matches = data["matches"]
    assert first["matches"] == second["matches"] == len(matches)
    assert first["wins"] == second["losses"] and first["losses"] == second["wins"]
    assert first["draws"] == second["draws"]
    assert first["goals_for"] == second["goals_against"]
    assert first["goals_against"] == second["goals_for"]
    assert first["goals_for"] + second["goals_for"] == sum(m["home_goals"] + m["away_goals"] for m in matches)
    for match in matches:
        assert {match["home_team_id"], match["away_team_id"]} == {team_a, team_b}
    for team in data["teams"]:
        assert team["wins"] + team["draws"] + team["losses"] == len(matches)
        assert team["points"] == 3 * team["wins"] + team["draws"]
        assert team["goal_difference"] == team["goals_for"] - team["goals_against"]
        if matches:
            assert data["enrichment_available"]
            assert abs(team["goals_per_match"] - team["goals_for"] / len(matches)) < 1e-9
        else:
            assert team["goals_per_match"] is None


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
        for row in season["rows"]:
            if row["played"]:
                assert row["goals_for"] - row["goals_against"] == row["goal_diff"]
                assert abs(row["goals_for_per_match"] - row["goals_for"] / row["played"]) < 1e-9
                assert abs(row["goals_against_per_match"] - row["goals_against"] / row["played"]) < 1e-9
                assert row["attack_rank"] is not None and row["defense_rank"] is not None
            else:
                assert row["goals_for"] is None and row["goals_against"] is None
                assert row["goal_diff"] is None and row["attack_rank"] is None and row["defense_rank"] is None
            assert abs(row["goals_conceded_per_match"] - round(row["total_goals_conceded"] / row["matches"], 2)) < 1e-9
            assert abs(row["clean_sheet_rate"] - round(row["total_clean_sheets"] / row["matches"], 3)) < 1e-9
            if row["played"]:
                assert row["attack_rank"] == 1 + sum(
                    other["goals_for_per_match"] > row["goals_for_per_match"] for other in season["rows"]
                )
                assert row["defense_rank"] == 1 + sum(
                    other["goals_against_per_match"] < row["goals_against_per_match"] for other in season["rows"]
                )
        comparable = [r for r in season["rows"] if r.get("position") is not None
                      and (r.get("played") or 0) >= 30 and r["matches"] >= .8 * r["played"]]
        assert season["position_correlation"]["n"] == len(comparable)
        first, second = season["rows"][:2]
        meetings = fetch(f"/api/head-to-head?team_a={first['team_id']}&team_b={second['team_id']}&competition={league['id']}&season=24%2F25")
        check_head_to_head(meetings, first["team_id"], second["team_id"])
        analysis = fetch(f"/api/analysis?competition={league['id']}&season=24%2F25")
        assert all(row["season_key"] < 2024 for row in analysis["rows"]), "Partial 25/26 must not be a target"
        assert len({(row["team_id"], row["season_name"]) for row in analysis["rows"]}) == len(analysis["rows"])
        checks.append(f"{league['id']}: GF/GA/GD, per-match ranks, complete season and head-to-head")
    chosen = fetch("/api/season?competition=IT1&season=24%2F25")["rows"][0]
    club = fetch(f"/api/clubs/{chosen['team_id']}?competition=IT1&season=24%2F25")
    assert all(row["competition_id"] == "IT1" for row in club["history"])
    inter = fetch("/api/clubs/46?competition=IT1&season=24%2F25")["current"]
    if inter["played"]:
        assert (inter["goals_for"], inter["goals_against"], inter["goal_diff"]) == (79, 35, 44)
        assert (inter["attack_rank"], inter["defense_rank"]) == (1, 2)
    else:
        assert inter["goals_for"] is None and inter["attack_rank"] is None
    assert inter["total_goals_conceded"] == 35
    assert inter["goals_conceded_per_match"] == 0.92
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
    check_head_to_head(meetings, 46, 5)
    reverse = fetch("/api/head-to-head?team_a=5&team_b=46&competition=IT1&season=24%2F25")
    assert reverse["teams"] == meetings["teams"][::-1]
    empty = fetch("/api/head-to-head?team_a=46&team_b=5&competition=IT1&season=20%2F21")
    check_head_to_head(empty, 46, 5)
    fetch("/api/head-to-head?team_a=46&team_b=46&competition=IT1&season=24%2F25", expected=422)
    fetch("/api/head-to-head?team_a=46&team_b=46%27%20OR%201=1&competition=IT1&season=24%2F25", expected=422)
    fetch("/api/head-to-head?team_a=46&team_b=11&competition=IT1&season=24%2F25", expected=404)
    checks.extend(["head-to-head totals and reversed clubs",
                   "head-to-head contracts across two seasons", "invalid head-to-head clubs rejected"])
    exported = list(csv.DictReader(io.StringIO(fetch("/api/export?competition=IT1&season=24%2F25"))))
    assert len(exported) == 20
    project = fetch("/api/project")
    assert project["course_source_verified"]
    assert project["defense_spend"] and project["defense_spend"]["n_observations"] > 0
    assert project["defense_spend"]["p_value"] > 0.05
    if project["position"]:
        assert project["position"]["n_observations"] > 0
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
