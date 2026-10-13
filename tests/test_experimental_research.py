"""Offline checks for Phase 4 research module; no API, odds or Streamlit."""
from types import SimpleNamespace

import pandas as pd
import pytest

from backtests.experimental_research import (
    fit_recent_form_model,
    preweek_features,
    report_record,
    run,
    tier_name,
)


def game(year, week, home, away, hs, aw, gid=None, location="Home"):
    return {
        "game_id": gid or f"{year}_{week:02d}_{away}_{home}",
        "season": year,
        "week": week,
        "game_type": "REG",
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aw,
        "location": location,
        "home_rest": 7,
        "away_rest": 7,
    }


def fixture():
    # Two matchups each week, four teams and distinct winners.
    data = []
    for year in range(2019, 2027):
        for week in range(1, 7):
            if week % 2:
                data.extend([
                    game(year, week, "DAL", "NYG", 28 + (week % 3), 18),
                    game(year, week, "GB", "SEA", 20, 24 + (year % 3)),
                ])
            else:
                data.extend([
                    game(year, week, "NYG", "GB", 15, 23 + (week % 4)),
                    game(year, week, "SEA", "DAL", 27, 30 + (year % 3)),
                ])
    return pd.DataFrame(data)


def test_same_week_cannot_see_another_games_result():
    schedule = pd.DataFrame([
        game(2025, 1, "DAL", "NYG", 31, 13),
        game(2025, 1, "SEA", "GB", 40, 10),
        game(2025, 2, "DAL", "SEA", 24, 17),
        game(2025, 2, "GB", "NYG", 17, 28),
        game(2025, 3, "DAL", "GB", 12, 20),
    ])
    original = preweek_features(schedule).set_index("game_id")
    updated = schedule.copy()
    updated.loc[updated["week"].eq(2), "home_score"] = 80
    changed = preweek_features(updated).set_index("game_id")
    assert original.loc["2025_02_SEA_DAL", "recent_margin_feature"] == changed.loc["2025_02_SEA_DAL", "recent_margin_feature"]
    assert original.loc["2025_02_NYG_GB", "recent_margin_feature"] == changed.loc["2025_02_NYG_GB", "recent_margin_feature"]
    assert original.loc["2025_02_SEA_DAL", "min_prior_games"] == 1
    assert original.loc["2025_02_SEA_DAL", "ppg_projected_margin"] == pytest.approx(
        ((31 + 10) - (40 + 13)) / 2 + 2
    )
    # Week 3 can legitimately change after Week 2 changes.
    assert original.loc["2025_03_GB_DAL", "recent_margin_feature"] != changed.loc["2025_03_GB_DAL", "recent_margin_feature"]


def test_2025_scoring_changes_cannot_change_2024_features():
    schedule = fixture()
    first = preweek_features(schedule).set_index("game_id")
    changed = schedule.copy()
    changed.loc[changed["season"].eq(2025), "home_score"] += 50
    second = preweek_features(changed).set_index("game_id")
    ids = first.index.str.startswith("2024_")
    pd.testing.assert_frame_equal(first.loc[ids], second.loc[ids])


def test_missing_and_duplicate_game_ids_fail_closed():
    with pytest.raises(ValueError, match="required"):
        preweek_features(pd.DataFrame({"game_id": ["a"]}))
    g = fixture().iloc[:1]
    with pytest.raises(ValueError, match="duplicate"):
        preweek_features(pd.concat([g, g], ignore_index=True))


def test_tiers_are_exclusive_and_research_only():
    row = lambda p, diff, n, pp: SimpleNamespace(
        pick_probability=p, home_probability=diff,
        min_prior_games=n, ppg_projected_margin=pp
    )
    assert tier_name(row(.78, .8, 0, None)).startswith("Tier 1")
    assert tier_name(row(.65, .7, 4, 9)).startswith("Tier 2")
    assert tier_name(row(.65, .7, 4, 5)).startswith("Tier 3")
    assert tier_name(row(.65, .7, 4, -9)).startswith("Tier 4")
    assert tier_name(row(.58, .7, 4, 9)).startswith("Tier 4")
    assert tier_name(row(.65, .7, 2, 9)).startswith("Tier 4")


def test_full_research_runs_and_does_not_mutate_schedule():
    schedule = fixture()
    baseline = schedule.copy(deep=True)
    results = run(schedule)
    pd.testing.assert_frame_equal(schedule, baseline)
    assert results["status"] == "RESEARCH_ONLY_NOT_DEPLOYED"
    assert results["fit_years"] == [2019, 2020, 2021, 2022]
    assert len(results["coefficients"]) == 3
    for key in ("2019-2022_training", "2023-2025_retrospective", "2026_preliminary"):
        period = results["periods"][key]
        assert period["baseline"]["games"] > 0
        assert sum(t["games"] for t in period["tiers"].values()) == period["baseline"]["games"]
    assert "odds" in " ".join(results["limitations"])


def test_training_refuses_any_2023_result():
    frame = pd.DataFrame({
        "season": [2022, 2023],
        "elo_difference_100": [1, 1],
        "recent_margin_feature": [0, 0],
        "actual_home_win": [True, False],
    })
    with pytest.raises(ValueError, match="2019"):
        fit_recent_form_model(frame)


def test_record_grades_from_true_home_outcomes():
    f = pd.DataFrame({
        "home_probability": [0.7, 0.2],
        "actual_home_win": [True, True],
    })
    r = report_record(f, "home_probability")
    assert r == {"games": 2, "wins": 1, "losses": 1, "accuracy": .5}
