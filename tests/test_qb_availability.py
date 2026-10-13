"""QB confirmation contracts: fail closed, pregame only, no Elo mutation."""
import pandas as pd
import pytest

from sunday_slate.qb_availability import (
    latest_depth, read_owner_confirmations, approved_announcement,
    dated_qb_injury, prior_qb_quality, prior_starter, context,
)
from sunday_slate.ui import qb_availability_panel


NOW="2026-10-10T16:00:00Z"
KO="2026-10-11T17:00:00Z"


def depth():
    return pd.DataFrame([
        dict(dt="2026-10-09T12:00:00Z",team="DAL",pos_abb="QB",pos_rank=1,
             gsis_id="00-0000001",player_name="Old Starter"),
        dict(dt="2026-10-09T12:00:00Z",team="DAL",pos_abb="QB",pos_rank=2,
             gsis_id="00-0000002",player_name="Potential Backup"),
        dict(dt="2026-10-10T13:00:00Z",team="DAL",pos_abb="QB",pos_rank=1,
             gsis_id="00-0000002",player_name="Potential Backup"),
        dict(dt="2026-10-10T13:00:00Z",team="DAL",pos_abb="QB",pos_rank=2,
             gsis_id="00-0000001",player_name="Old Starter"),
        dict(dt="2026-10-11T18:00:00Z",team="DAL",pos_abb="QB",pos_rank=1,
             gsis_id="00-0000003",player_name="Future Unavailable"),
        dict(dt="2026-10-10T13:00:00Z",team="NYG",pos_abb="QB",pos_rank=1,
             gsis_id="00-0000004",player_name="Visitor"),
    ])


def schedule():
    return pd.DataFrame([
        dict(season=2026,week=5,game_type="REG",game_id="2026_05_DAL_NYG",
             home_team="NYG",away_team="DAL",home_qb_id="00-0000004",
             away_qb_id="00-0000001",home_score=17,away_score=14),
        dict(season=2026,week=6,game_type="REG",game_id="2026_06_DAL_NYG",
             home_team="NYG",away_team="DAL",home_qb_id=None,
             away_qb_id=None,home_score=None,away_score=None),
    ])


def game():
    return dict(season=2026,week=6,game_id="2026_06_DAL_NYG",
                home_team="NYG",away_team="DAL",kickoff_ct=KO)


def players():
    return pd.DataFrame([
        dict(season=2026,week=5,position="QB",player_id="00-0000001",
             passing_epa=12.,attempts=45,sacks_suffered=5,season_type="REG"),
        dict(season=2026,week=5,position="QB",player_id="00-0000002",
             passing_epa=2.,attempts=20,sacks_suffered=0,season_type="REG"),
        dict(season=2026,week=6,position="QB",player_id="00-0000002",
             passing_epa=999999.,attempts=35,sacks_suffered=0,season_type="REG"),
    ])


def test_uses_latest_prior_dated_qb1_and_actual_ranked_backup():
    previous=latest_depth(depth(),"DAL","2026-10-10T12:00:00Z")
    assert previous["starter"]["gsis_id"]=="00-0000001"
    current=latest_depth(depth(),"DAL","2026-10-10T16:00:00Z")
    assert current["starter"]["gsis_id"]=="00-0000002"
    assert current["backup"]["gsis_id"]=="00-0000001"
    assert current["asof"].startswith("2026-10-10")


def test_missing_or_future_or_old_depth_never_marked_confirmed():
    assert latest_depth(depth(),"DAL","2026-10-01T00:00:00Z")["starter"] is None
    assert latest_depth(depth(),"DAL","2026-11-15T00:00:00Z")["starter"] is None
    assert latest_depth(depth().drop(columns="dt"),"DAL",NOW)["starter"] is None


def test_owner_announcements_require_public_nfl_url_and_before_kickoff():
    valid={"2026_06_DAL_NYG":{"DAL":{
        "gsis_id":"00-0000002","player_name":"Potential Backup",
        "reported_at":"2026-10-10T15:00:00Z",
        "source_url":"https://www.nfl.com/news/a-football-announcement"}}}
    assert read_owner_confirmations('{"a":{}}')=={"a":{}}
    assert read_owner_confirmations("{bad")=={}
    assert approved_announcement(valid,"2026_06_DAL_NYG","DAL",NOW,KO)
    item=valid["2026_06_DAL_NYG"]["DAL"]
    for url in ("https://nfl.com.evil.com/story",
                "http://www.nfl.com/story",
                "https://evil.org/story"):
        assert approved_announcement(valid,"2026_06_DAL_NYG","DAL",NOW,KO) is not None
        item["source_url"]=url
        assert approved_announcement(valid,"2026_06_DAL_NYG","DAL",NOW,KO) is None
        item["source_url"]="https://www.nfl.com/news/a-football-announcement"
    item["reported_at"]="2026-10-11T18:00:00Z"
    assert approved_announcement(valid,"2026_06_DAL_NYG","DAL","2026-10-11T19:00:00Z",KO) is None
    item["reported_at"]="2026-10-10T17:00:00Z"
    assert approved_announcement(valid,"2026_06_DAL_NYG","DAL",NOW,KO) is None


def test_report_status_requires_actual_timestamp_and_never_guesses_healthy():
    sample=pd.DataFrame([
       dict(season=2026,week=6,team="DAL",gsis_id="00-0000002",
            position="QB",report_status="Questionable",
            date_modified="2026-10-10T14:00:00Z"),
       dict(season=2026,week=6,team="DAL",gsis_id="00-0000002",
            position="QB",report_status="Out",
            date_modified="2026-10-12T12:00:00Z"),
    ])
    actual=dated_qb_injury(sample,2026,6,"DAL","00-0000002",NOW,KO)
    assert actual["status"]=="Questionable"
    assert dated_qb_injury(sample.drop(columns="date_modified"),2026,6,
                           "DAL","00-0000002",NOW,KO) is None
    assert dated_qb_injury(sample,2026,5,"DAL","00-0000002",NOW,KO) is None


def test_qb_quality_is_prior_week_only_and_missing_is_unknown():
    a=prior_qb_quality(players(),2026,6,"00-0000002")
    assert a["epa_per_dropback"]==pytest.approx(2/(20+150),abs=.0001)
    assert prior_qb_quality(players(),2026,5,"00-0000002") is None
    assert prior_starter(schedule(),"DAL",2026,6)["gsis_id"]=="00-0000001"


def test_render_labels_projections_and_does_not_change_elo():
    out=context(game(),schedule(),depth(),players(),pd.DataFrame(),{},NOW)
    info=out["teams"]["DAL"]
    assert info["expected"]["gsis_id"]=="00-0000002"
    assert info["replacement_delta_epa"]==pytest.approx(
        round(2/170-12/200,4),abs=.0001)
    assert out["official_elo_unchanged"]
    panel=qb_availability_panel(out)
    assert "unconfirmed" in panel.lower()
    assert "Elo" in panel and "replacement" in panel.lower()
    assert "Future Unavailable" not in panel


def test_depth_chart_cannot_override_source_dated_out_without_caution():
    injured=pd.DataFrame([dict(season=2026,week=6,team="DAL",
       gsis_id="00-0000002",position="QB",report_status="Out",
       date_modified="2026-10-10T15:00:00Z")])
    out=context(game(),schedule(),depth(),players(),injured,{},NOW)
    assert "OUT" in out["teams"]["DAL"]["classification"]
    assert out["teams"]["DAL"]["confirmation"] is None


def test_higher_quality_is_not_assigned_when_one_qb_unrated():
    x=context(game(),schedule(),depth(),players().loc[lambda d:d.player_id.ne("00-0000002")],
              None,{},NOW)
    assert x["teams"]["DAL"]["replacement_delta_epa"] is None
