"""Unit checks for immutable candidate parameters and mutually exclusive tier logic."""
from datetime import datetime, timezone
import json

import pandas as pd
import pytest

from research.frozen_weekly import (
    load_frozen, challenger_probability, select_upcoming_week, grade_archive,
)
from research.tiers_validation import classify, TIER_NAMES


def test_frozen_candidate_is_deterministic_and_not_refitted():
    cfg = load_frozen()
    row = {key: cfg["mean"][i] for i, key in enumerate(cfg["columns"])}
    got = challenger_probability(row, cfg)
    assert got == pytest.approx(1 / (1 + __import__("math").exp(-cfg["intercept"])))
    assert challenger_probability(row, cfg) == got
    assert cfg["version"] == "NFL-FORM-EPA-RESEARCH-20261013-v1"


@pytest.mark.parametrize(("elo", "ppg", "n", "tier"), [
    (.78, None, 0, 0), (.61, 8., 4, 1), (.61, 5., 4, 2),
    (.61, -8., 4, 3), (.56, 9., 5, 3), (.68, 9., 1, 3),
])
def test_tier_waterfall_is_exclusive(elo, ppg, n, tier):
    game = {"pick_probability": elo,
            "home_probability": elo,
            "ppg_projected_margin": ppg,
            "min_prior_games": n}
    assert classify(game) == TIER_NAMES[tier]


def test_never_create_current_week_after_kickoff_date():
    preds = pd.DataFrame([
        {"game_id": "2026_06_X_Y", "season": 2026, "week": 6,
         "home_team": "Y", "away_team": "X"},
        {"game_id": "2026_07_Y_X", "season": 2026, "week": 7,
         "home_team": "X", "away_team": "Y"},
    ])
    sched = pd.DataFrame([
        {"game_id": "2026_06_X_Y", "gameday": "2026-10-15",
         "home_score": None, "away_score": None},
        {"game_id": "2026_07_Y_X", "gameday": "2026-10-22",
         "home_score": None, "away_score": None},
    ])
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    year, week, got = select_upcoming_week(preds, sched, now)
    assert (year, week, len(got)) == (2026, 6, 1)


def test_grade_frozen_archive_without_changing_it(tmp_path):
    records = [
        {"game_id": "2026_06_A_B", "home_team": "B", "away_team": "A",
         "elo_winner": "B", "challenger_winner": "A"},
        {"game_id": "2026_06_C_D", "home_team": "D", "away_team": "C",
         "elo_winner": "C", "challenger_winner": "C"},
    ]
    sample = {"season": 2026, "week": 6, "games": records,
              "snapshot_sha256": "frozen-123"}
    path = tmp_path / "2026_week_06.json"
    path.write_text(json.dumps(sample))
    initial = path.read_bytes()
    results = grade_archive(pd.DataFrame([
        {"game_id": "2026_06_A_B", "home_score": 14, "away_score": 21},
        {"game_id": "2026_06_C_D", "home_score": None, "away_score": None},
    ]), tmp_path)
    week = results["snapshots"][0]
    assert week["graded"] == 1 and week["pending_or_tie"] == 1
    assert week["elo"]["wins"] == 0
    assert week["challenger"]["wins"] == 1
    assert initial == path.read_bytes()


def test_bad_frozen_config_is_rejected(tmp_path):
    p = tmp_path / "params.json"
    p.write_text(json.dumps({"columns": ["dummy"],
        "training_years": [2019, 2020, 2021, 2022]}))
    with pytest.raises(ValueError):
        load_frozen(p)
