"""Offline checks for new success-rate / opponent-adjusted EPA experiment."""
import numpy as np
import pandas as pd
import pytest

from research.rush_success_adjusted import (
    RIDGE_EQUIV_PLAYS, _candidate, _validate_aggregates,
    adjusted_ratings, grade,
)


def test_no_lookahead_adjustment_uses_only_passed_prior_game_lines():
    lines=[
        {"posteam": "A", "defteam": "B", "n": 20., "rush_epa_sum": 12.},
        {"posteam": "B", "defteam": "A", "n": 20., "rush_epa_sum": -8.},
        {"posteam": "C", "defteam": "D", "n": 20., "rush_epa_sum": 6.},
        {"posteam": "D", "defteam": "C", "n": 20., "rush_epa_sum": -6.},
        {"posteam": "A", "defteam": "C", "n": 25., "rush_epa_sum": 8.},
        {"posteam": "C", "defteam": "A", "n": 25., "rush_epa_sum": -7.},
        {"posteam": "B", "defteam": "D", "n": 25., "rush_epa_sum": 2.},
        {"posteam": "D", "defteam": "B", "n": 25., "rush_epa_sum": -10.},
        {"posteam": "A", "defteam": "D", "n": 23., "rush_epa_sum": 4.},
        {"posteam": "D", "defteam": "A", "n": 23., "rush_epa_sum": -12.},
    ]
    teams={"A", "B", "C", "D"}
    first=adjusted_ratings(lines,teams)
    assert set(first)==teams
    assert all(np.isfinite(x["off"]) and np.isfinite(x["def"]) for x in first.values())
    assert RIDGE_EQUIV_PLAYS>0
    # Future-week games do not enter a prediction unless appended to history.
    future={"posteam":"A","defteam":"B","n":20.,"rush_epa_sum":400.}
    assert adjusted_ratings(lines,teams)==first
    changed=adjusted_ratings(lines+[future],teams)
    assert changed["A"]["off"]!=pytest.approx(first["A"]["off"])


def test_signal_symmetric_and_ambiguous_excluded():
    metric={"A":{"off":.58,"def":-.15},"B":{"off":-.6,"def":.22}}
    assert _candidate("A","B",metric,"off","def",-.4,0)=="A"
    assert _candidate("B","A",metric,"off","def",-.4,0)=="A"
    assert _candidate("A","B",metric,"off","def",-1,0) is None
    two={"A":{"off":-.6,"def":-.5},"B":{"off":-.6,"def":-.5}}
    assert _candidate("A","B",two,"off","def",-.4,-.4) is None


def test_invalid_and_duplicated_game_rush_summaries_fail_closed():
    one=pd.DataFrame([dict(season=2025,week=1,game_id="g1",posteam="A",
                           defteam="B",n=20,rush_epa_sum=-1,successes=11)])
    with pytest.raises(ValueError,match="Duplicate"):
        _validate_aggregates(pd.concat([one,one],ignore_index=True))
    with pytest.raises(ValueError,match="Impossible"):
        _validate_aggregates(one.assign(successes=99))


def test_success_and_elo_compared_same_games_excluding_spread_pushes():
    x=pd.DataFrame([
        dict(signal_team="A",winner="A",elo_team="B",cover=True),
        dict(signal_team="A",winner="B",elo_team="B",cover=False),
        dict(signal_team="A",winner="A",elo_team="A",cover=None),
    ])
    r=grade(x)
    assert r["signal"]=={"games":3,"wins":2,"losses":1,"pct":66.67}
    assert r["elo_same_games"]["wins"]==2
    assert r["against_elo"]=={"games":2,"signal_wins":1,"elo_wins":1,"net_changed_correct":0}
    assert r["historical_spread"]=={"games":2,"covers":1,"noncovers":1,"pct":50.,"excluded_pushes_missing":1}
