"""Parlay research should fail closed rather than fabricate current lines or forecasts."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from sunday_slate.parlay import (
    CORE_SOURCE, ELO_SOURCE, SORT_CHANCE, SORT_VALUE, decimal_to_american,
    eligible_legs, find_parlays,
)

NOW = pd.Timestamp("2026-10-20T15:00:00Z")


def fixtures():
    slate = pd.DataFrame([
        {"game_id": "1", "home_team": "KC", "away_team": "LV",
         "kickoff_ct": NOW + pd.Timedelta(days=1), "completed": False},
        {"game_id": "2", "home_team": "BUF", "away_team": "MIA",
         "kickoff_ct": NOW + pd.Timedelta(days=2), "completed": False},
        {"game_id": "3", "home_team": "DAL", "away_team": "PHI",
         "kickoff_ct": NOW + pd.Timedelta(days=2), "completed": False},
        {"game_id": "4", "home_team": "NYJ", "away_team": "NE",
         "kickoff_ct": NOW + pd.Timedelta(days=1), "completed": False},
    ])
    quotes = {
        "1": {"source": "DraftKings", "home_moneyline": -200, "away_moneyline": 170},
        "2": {"source": "DraftKings", "home_moneyline": -150, "away_moneyline": 135},
        "3": {"source": "DraftKings", "home_moneyline": 120, "away_moneyline": -135},
        "4": {"source": "DraftKings", "home_moneyline": -110, "away_moneyline": 100},
    }
    picks = {
        "1": {"predicted_winner": "KC", "home_probability": .78},
        "2": {"predicted_winner": "BUF", "home_probability": .69},
        "3": {"predicted_winner": "PHI", "home_probability": .74},
        "4": {"predicted_winner": "NYJ", "home_probability": .56},
    }
    core = [
        {"game_id": gid, "home_team": h, "away_team": a, "team": winner,
         "probability": p, "tier": tier}
        for gid, h, a, winner, p, tier in [
            ("1", "KC", "LV", "KC", .78, 1),
            ("2", "BUF", "MIA", "BUF", .69, 2),
        ]
    ]
    return slate, quotes, picks, core


def test_elo_parlay_math_and_rank():
    slate, quotes, predictions, _ = fixtures()
    legs = eligible_legs(slate, quotes, predictions, now=NOW)
    assert [leg["team"] for leg in legs] == ["KC", "PHI", "BUF"]
    ranked = find_parlays(legs)
    assert ranked[0]["probability"] == pytest.approx(.78 * .74)
    assert ranked[0]["decimal"] == pytest.approx(1.5 * (1 + 100 / 135))
    assert ranked[0]["break_even"] == pytest.approx(1 / ranked[0]["decimal"])
    assert ranked[0]["estimated_roi"] == pytest.approx(ranked[0]["probability"] * ranked[0]["decimal"] - 1)
    assert ranked[0]["payout_10"] == pytest.approx(10 * ranked[0]["decimal"])
    assert all(len(set(leg["game_id"] for leg in row["legs"])) == 2 for row in ranked)
    assert len(find_parlays(legs, count=4)) == 0
    assert decimal_to_american(3.5) == "+250"
    assert decimal_to_american(1.5) == "-200"


def test_core_source_only_from_verified_core():
    slate, quotes, predictions, core = fixtures()
    legs = eligible_legs(slate, quotes, predictions, core, source=CORE_SOURCE, now=NOW)
    assert {leg["game_id"] for leg in legs} == {"1", "2"}
    assert len(find_parlays(legs, 2)) == 1
    assert not eligible_legs(slate, quotes, predictions, [], source=CORE_SOURCE, now=NOW)


def test_reject_started_completed_wrong_book_bad_and_partial_prices():
    slate, quotes, predictions, core = fixtures()
    slate.loc[0, "kickoff_ct"] = NOW
    slate.loc[1, "completed"] = True
    quotes["3"]["source"] = "FanDuel"
    quotes["4"]["home_moneyline"] = None
    assert eligible_legs(slate, quotes, predictions, core, now=NOW) == []
    slate, quotes, predictions, core = fixtures()
    quotes["1"]["away_moneyline"] = None
    quotes["2"]["home_moneyline"] = -1200
    quotes["2"]["away_moneyline"] = 150  # Invalid overround
    assert {x["game_id"] for x in eligible_legs(slate, quotes, predictions, now=NOW)} == {"3"}


def test_no_retroactive_picks_or_opposite_winner_and_dedup():
    slate, quotes, predictions, core = fixtures()
    predictions["1"]["predicted_winner"] = "LV"
    slate = pd.concat([slate, slate.iloc[[2]]], ignore_index=True)
    candidates = eligible_legs(slate, quotes, predictions, now=NOW)
    assert [x["game_id"] for x in candidates] == ["3", "2"]
    assert not eligible_legs(slate, quotes, predictions, now=NOW + pd.Timedelta(days=3))
    dupes = [candidates[0], candidates[0], candidates[1]]
    assert len(find_parlays(dupes, 2)) == 2
    assert find_parlays(dupes, 3) == []


def test_value_ranking_and_invalid_requests():
    slate, quotes, predictions, core = fixtures()
    legs = eligible_legs(slate, quotes, predictions, now=NOW)
    by_chance = find_parlays(legs, 2, sort_by=SORT_CHANCE)
    by_value = find_parlays(legs, 2, sort_by=SORT_VALUE)
    assert len(by_chance) == len(by_value) == 3
    assert by_value[0]["estimated_roi"] >= by_value[1]["estimated_roi"]
    assert find_parlays(legs, 5) == []
    assert find_parlays(legs, 2, sort_by="random") == []
