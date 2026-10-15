"""UI regression checks for the ranked weekly shortlist."""
from __future__ import annotations

import pandas as pd

from sunday_slate.shortlist_ui import _pick_card, _reason, _history_table


def test_core_pick_is_ranked_and_uses_plain_language():
    row = {
        "game_id": "g1", "team": "SF", "home_team": "SF",
        "away_team": "WAS", "tier": 1, "probability": .78,
        "ppg_agrees": True, "ppg_margin": 11.5,
    }
    games = pd.DataFrame([{
        "game_id": "g1", "completed": False,
        "kickoff_ct": pd.Timestamp("2026-10-20T00:15:00Z"),
    }])
    brands = {"SF": {"name": "San Francisco 49ers"},
              "WAS": {"name": "Washington Commanders"}}
    quotes = {"g1": {"source": "DraftKings", "home_moneyline": -425}}
    html = _pick_card(row, games, brands, quotes, rank=1)
    assert "#1" in html
    assert "Heavy Favorite" in html
    assert "San Francisco 49ers" in html
    assert "over Washington Commanders" in html
    assert "78.0% win chance" in html
    assert "11.5-point scoring edge" in html
    assert "DK -425 · delayed" in html
    assert "Why it qualifies" in html
    assert "Elo" not in html and "challenger" not in html


def test_missing_quote_is_not_invented_and_candidate_is_separate():
    row = {
        "game_id": "g2", "team": "NE", "home_team": "NE",
        "away_team": "NYJ", "tier": None, "probability": .70,
        "ppg_agrees": False, "ppg_margin": None,
        "reason": "Scoring confirmation unavailable",
    }
    games = pd.DataFrame([{"game_id": "g2", "completed": False,
                           "kickoff_ct": pd.NaT}])
    html = _pick_card(row, games, {}, potential=True)
    assert "Research only" in html
    assert "Potential addition" in html
    assert "Not enough scoring information" in html
    assert "DK " not in html
    assert "scoring edge" not in html
    assert _reason(row, True) == "Not enough scoring information"


def test_team_names_are_escaped():
    row = {
        "game_id": "g3", "team": "SF", "home_team": "SF",
        "away_team": "WAS", "tier": 3, "probability": .67,
        "ppg_agrees": False, "ppg_margin": None,
    }
    html = _pick_card(row, pd.DataFrame(columns=["game_id"]), {
        "SF": {"name": "<script>alert(1)</script>"},
        "WAS": {"name": "Washington & Friends"},
    }, rank=2)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Washington &amp; Friends" in html


def test_history_rows_keep_source_records():
    html = _history_table([("2025", {"wins": 52, "losses": 15})])
    assert "52–15" in html
    assert "77.6%" in html
    assert "2025" in html
