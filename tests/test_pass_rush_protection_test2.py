"""Offline quality gates for pass rush vs offensive protection Test 2."""
import pandas as pd
import pytest

from research.pass_rush_protection_test2 import (
    features_schedule, validate_agg, evaluate_predictions,
)


def schedule():
    games=[
        (1,"ATL","DAL",25,20),
        (1,"CHI","NYG",14,28),
        (2,"ATL","CHI",24,19),
        (2,"DAL","NYG",10,23),
        (3,"ATL","NYG",7,13),
        (3,"CHI","DAL",33,15),
    ]
    return pd.DataFrame([
       {"season":2024,"week":w,"game_id":f"2024_{w:02}_{a}_{h}",
        "game_type":"REG","home_team":h,"away_team":a,
        "home_score":hs,"away_score":aws,"spread_line":2.5}
       for w,h,a,hs,aws in games
    ])


def aggregates():
    rows=[]
    for g in schedule().to_dict("records"):
        for team,opponent,pressure,sack in (
                (g["home_team"],g["away_team"],6,2),
                (g["away_team"],g["home_team"],12,3)):
            rows.append({"season":2024,"week":g["week"],"game_id":g["game_id"],
               "posteam":team,"defteam":opponent,
               "dropbacks":30,"hit_observed":30,
               "pressures":pressure,"sacks":sack})
    return pd.DataFrame(rows)


def test_pregame_matchups_freeze_all_games_week():
    games=schedule()
    initial=features_schedule(games,validate_agg(aggregates()))[0].set_index("game_id")
    assert initial.loc["2024_01_DAL_ATL","min_games"]==0
    assert initial.loc["2024_02_CHI_ATL","min_games"]==1
    assert initial.loc["2024_03_NYG_ATL","min_games"]==2
    assert initial.loc["2024_01_DAL_ATL","raw_edge"]==0
    assert initial.loc["2024_01_NYG_CHI","raw_edge"]==0
    updated=aggregates()
    changed=updated.game_id.eq("2024_02_CHI_ATL")&updated.posteam.eq("ATL")
    updated.loc[changed,"pressures"]=27
    updated.loc[changed,"sacks"]=15
    test=features_schedule(games,validate_agg(updated))[0].set_index("game_id")
    for name in ("raw_edge","adjusted_edge","recent_edge","sack_edge"):
        assert test.loc["2024_02_CHI_ATL",name]==pytest.approx(initial.loc["2024_02_CHI_ATL",name])
        assert test.loc["2024_02_NYG_DAL",name]==pytest.approx(initial.loc["2024_02_NYG_DAL",name])
    assert test.loc["2024_03_NYG_ATL","raw_edge"]!=pytest.approx(
        initial.loc["2024_03_NYG_ATL","raw_edge"])


def test_nflverse_home_favored_spread_ats_conversion():
    games=pd.DataFrame({
        "actual_home_win":[1,1,0],
        "home_score":[30,24,17],
        "away_score":[20,23,30],
        "spread_line":[7,3,-13],
    })
    result=evaluate_predictions(games,pd.Series([.9,.8,.4]))
    assert result["games"]==3
    # Home covers first. Away covers second despite home SU win. Third pushes.
    assert result["ats_with_reference_line"]=={
        "wins":2,"losses":0,"push":1,"cover_pct":100.0}


def test_bad_aggregates_fail_closed():
    x=aggregates()
    with pytest.raises(ValueError,match="duplicate|Ambiguous"):
        validate_agg(pd.concat([x,x.iloc[[0]]],ignore_index=True))
    x.loc[0,"pressures"]=100
    with pytest.raises(ValueError,match="impossible"):
        validate_agg(x)
