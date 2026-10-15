import pandas as pd
from research.shortlist_nearmisses import eligible, select_week


def fixture():
    def make(gid,confidence,margin,outcome="Correct"):
        return dict(game_id=gid, season=2026,week=5,home_team=gid,away_team="OPP",
                    predicted_winner=gid,home_probability=confidence,
                    pick_probability=confidence,challenger_home_probability=confidence,
                    ppg_projected_margin=margin,min_prior_games=5,pick_result=outcome)
    return pd.DataFrame([make("CORE",.78,8),
                         make("NEAR",.64,1.1),make("RUSH",.61,-5),
                         make("OTHER",.58,-2)])


def test_target_three_without_replacing_core():
    frame=fixture()
    team, added, pool=select_week(frame,"Loose PPG + challenger",{}, {},3)
    assert [r["game_id"] for r in team]==["CORE","NEAR"]
    assert [r["game_id"] for r in added]==["NEAR"]


def test_rushing_support_does_not_override_elo():
    frame=fixture()
    result,added,_=select_week(frame,"Rush support + challenger",{"RUSH":"RUSH","OTHER":"OPP"},{},3)
    assert [r["game_id"] for r in result]==["CORE","RUSH"]


def test_picks_do_not_depend_on_target_week_results():
    frame=fixture()
    other=frame.copy()
    other["pick_result"]="Incorrect"
    for kind in ("Loose PPG + challenger","Strong Elo + challenger",
                 "PPG or rushing support + challenger"):
        a=select_week(frame,kind,{"RUSH":"RUSH"},{},5)[0]
        b=select_week(other,kind,{"RUSH":"RUSH"},{},5)[0]
        assert [r["game_id"] for r in a]==[r["game_id"] for r in b]
