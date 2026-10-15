"""Regression checks for the centralized weekly movement tables."""
import pandas as pd

from sunday_slate.line_movement import capture
from sunday_slate.line_movement_table import weekly_tables


def game():
    return {
        "season": 2026, "game_id": "2026_07_SEA_DEN", "away_team": "SEA",
        "home_team": "DEN", "kickoff_ct": pd.Timestamp("2026-12-01T01:00:00Z"),
        "completed": False,
    }


def quote(home_spread, home_ml, away_ml):
    return {
        "source": "DraftKings", "feed": "ESPN",
        "home_spread": home_spread, "away_spread": -home_spread,
        "home_moneyline": home_ml, "away_moneyline": away_ml,
    }


def test_spread_movement_toward_away_and_ml_probabilities():
    fixture = game()
    archive = {"schema_version": 1, "games": {}}
    assert capture(archive, fixture, quote(-3.5, -175, 150),
                   captured_at="2026-10-14T14:00:00Z")
    assert capture(archive, fixture, quote(-2, -130, 115),
                   captured_at="2026-10-15T14:00:00Z")
    spreads, mls, tracked, moved = weekly_tables(pd.DataFrame([fixture]), archive)
    assert (tracked, moved) == (1, 1)
    line = spreads.iloc[0]
    assert line["Matchup"] == "SEA @ DEN"
    assert line["Home · first"] == "-3.5"
    assert line["Home · latest"] == "-2"
    assert line["Shift (pts)"] == "+1.5"
    assert line["Direction"] == "Toward SEA"
    assert line["_changed"]
    assert mls.iloc[0]["Movement"] == "Shortened"
    assert mls.iloc[1]["Movement"] == "Lengthened"
    assert "10/15" in line["Observed (CT)"]


def test_missing_history_does_not_invent_opening_line():
    spreads, mls, tracked, moved = weekly_tables(
        pd.DataFrame([game()]), {"games": {}}
    )
    assert tracked == moved == 0
    assert spreads.iloc[0]["Home · first"] == "—"
    assert spreads.iloc[0]["Direction"] == "Unavailable"
    assert not mls["_changed"].any()


def test_moneyline_change_across_pickem_sign_change():
    fixture = game()
    archive = {"games": {}}
    capture(archive, fixture, quote(0, 100, -120),
            captured_at="2026-10-14T14:00:00Z")
    capture(archive, fixture, quote(0, -110, -105),
            captured_at="2026-10-15T14:00:00Z")
    spreads, mls, tracked, moved = weekly_tables(pd.DataFrame([fixture]), archive)
    assert (tracked, moved) == (1, 1)
    assert spreads.iloc[0]["Direction"] == "Unchanged"
    home = mls[mls["Team"] == "DEN"].iloc[0]
    assert home["ML · first"] == "+100"
    assert home["ML · latest"] == "-110"
    assert home["Movement"] == "Shortened"
