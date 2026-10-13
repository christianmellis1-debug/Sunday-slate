"""Offline regression tests for the Phase 4 opponent-adjusted EPA/QBR research."""
import pandas as pd
import pytest

from research.model_epa_qbr_study import make_features, evaluate, load_stats


def game(week, home, away, home_score, away_score):
    return {
        "game_id": f"2024_{week:02d}_{away}_{home}", "season": 2024,
        "game_type": "REG", "week": week,
        "home_team": home, "away_team": away,
        "home_score": home_score, "away_score": away_score,
        "home_rest": 7, "away_rest": 7, "location": "Home",
    }


def game_stats(g, hpass=8., apass=-2.):
    base = []
    for team, opponent, pe in (
        (g["home_team"], g["away_team"], hpass),
        (g["away_team"], g["home_team"], apass)
    ):
        base.append({
            "season": 2024, "week": g["week"], "game_id": g["game_id"],
            "season_type": "REG", "team": team, "opponent_team": opponent,
            "passing_epa": pe, "attempts": 20,
            "rushing_epa": pe/2, "carries": 20,
        })
    return base


def fixture():
    games=[
        game(1, "DAL", "NYG", 26, 14),
        game(1, "GB", "SEA", 21, 17),
        game(2, "DAL", "SEA", 18, 16),
        game(2, "NYG", "GB", 13, 20),
        game(3, "NYG", "DAL", 23, 14),
        game(3, "SEA", "GB", 28, 27),
    ]
    stats=[]
    for g in games:
        stats.extend(game_stats(g))
    qbr=pd.DataFrame(columns=["season","week_num","player_id","team_abb","qbr_total","qb_plays"])
    return pd.DataFrame(games),pd.DataFrame(stats),qbr


def test_pregame_epa_excludes_current_and_future_week():
    games,stats,qbr=fixture()
    first=make_features(games,stats,qbr).set_index("game_id")
    assert first.loc["2024_01_NYG_DAL","min_games"] == 0
    assert first.loc["2024_02_SEA_DAL","min_games"] == 1
    assert first.loc["2024_03_DAL_NYG","min_games"] == 2
    updated=stats.copy()
    # Change only one club: a symmetric change to every team could cancel.
    updated.loc[updated["game_id"].eq("2024_02_SEA_DAL") & updated["team"].eq("DAL"),"passing_epa"] = 900.
    second=make_features(games,updated,qbr).set_index("game_id")
    # No week-2 input can be modified by same week's final box scores.
    for col in ("p_raw","p_adj","r_raw","r_adj"):
        assert first.loc["2024_02_SEA_DAL",col] == pytest.approx(second.loc["2024_02_SEA_DAL",col])
        assert first.loc["2024_02_GB_NYG",col] == pytest.approx(second.loc["2024_02_GB_NYG",col])
    assert first.loc["2024_03_DAL_NYG","p_adj"] != second.loc["2024_03_DAL_NYG","p_adj"]


def test_qbr_missing_is_explicitly_zero_coverage():
    games,stats,qbr=fixture()
    got=make_features(games,stats,qbr)
    assert got.qb_both_known.eq(0).all()
    assert got.qbr_delta.eq(0).all()


def test_scores_are_not_used_to_fit_features():
    games,stats,qbr=fixture()
    old=make_features(games,stats,qbr).set_index("game_id")
    revised=games.copy()
    revised.loc[revised.week.eq(2),"home_score"]=100
    revised.loc[revised.week.eq(2),"away_score"]=0
    new=make_features(revised,stats,qbr).set_index("game_id")
    pd.testing.assert_series_equal(old.loc["2024_02_SEA_DAL"],new.loc["2024_02_SEA_DAL"])
    pd.testing.assert_series_equal(old.loc["2024_03_DAL_NYG"],new.loc["2024_03_DAL_NYG"])


def test_evaluation_uses_decisive_winners_without_fabricated_records():
    f=pd.DataFrame({"actual_home_win":[True,False,False]})
    got=evaluate(f,[.6,.8,.3])
    assert got["n"]==3 and got["wins"]==2 and got["losses"]==1
    assert 0<got["brier"]<1
