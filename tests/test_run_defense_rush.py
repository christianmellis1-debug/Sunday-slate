"""Regression tests for run-defense/rush-offense scenario screening.

The research is separate from the user-facing model; no rule is deployed.
"""
import pandas as pd

from research.run_defense_rush import _selection, _snapshot, ats_rate, select_training_rule


def test_league_snapshot_uses_prior_game_ypc_totals_only():
    data = {
        "DEF": dict(games=3, carries=70, rush_yards=350, opp_carries=80, opp_rush_yards=160),
        "WEAK": dict(games=3, carries=90, rush_yards=180, opp_carries=75, opp_rush_yards=375),
        "UNREADY": dict(games=2, carries=50, rush_yards=100, opp_carries=50, opp_rush_yards=100),
    }
    ranks, off, defensive = _snapshot(data, min_games=3)
    assert set(ranks) == {"DEF", "WEAK"}
    assert ranks["DEF"]["rush_allowed_ypc"] == 2.0
    assert ranks["WEAK"]["rush_ypc"] == 2.0
    assert len(off) == 2 and len(defensive) == 2


def test_run_defense_signal_is_symmetric_and_ambiguous_games_are_excluded():
    rankings = {
        "DEF": {"rush_allowed_ypc": 2., "rush_ypc": 5.},
        "WEAK": {"rush_allowed_ypc": 5., "rush_ypc": 2.},
    }
    assert _selection("DEF", "WEAK", rankings, weak_cut=2.5, strong_cut=2.5) == "DEF"
    assert _selection("WEAK", "DEF", rankings, weak_cut=2.5, strong_cut=2.5) == "DEF"
    assert _selection("DEF", "WEAK", rankings, weak_cut=1.5, strong_cut=2.5) is None
    same = {name: {"rush_allowed_ypc": 2., "rush_ypc": 2.} for name in ("DEF", "WEAK")}
    assert _selection("DEF", "WEAK", same, weak_cut=2.5, strong_cut=2.5) is None


def test_missing_spread_and_push_do_not_count_as_cover_losses():
    data = pd.DataFrame([
        {"cover": True}, {"cover": False}, {"cover": None}, {"cover": None},
    ])
    result = ats_rate(data)
    assert result == {"games": 2, "wins": 1, "losses": 1, "pct": 50., "ungraded": 2}


def test_no_positive_override_never_selects_unvalidated_signal():
    evaluated = [
        {"quantile": .20, "signal_winner": {"games": 60},
         "signal_overrides_elo": {"games": 30}, "net_changes_if_override": -5},
        {"quantile": .25, "signal_winner": {"games": 75},
         "signal_overrides_elo": {"games": 36}, "net_changes_if_override": 0},
    ]
    assert select_training_rule(evaluated) is None
