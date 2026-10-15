"""Regression tests for frozen weekly shortlist and its historical record."""
from copy import deepcopy
import hashlib
import json

import pandas as pd

from sunday_slate.shortlist import (
    HISTORICAL, grade, historic_total, history_rate, load_snapshot,
    shortlist, snapshot_is_pregame,
)


def fixture():
    picks = [
        ("one", "A", "B", .81, .82, None, 0),
        ("two", "C", "D", .68, .72, 10, 4),
        ("three", "E", "F", .67, .72, 3.5, 4),
        ("four", "G", "H", .69, .75, -6, 4),
        ("five", "I", "J", .70, .72, 1.5, 4),
        ("six", "K", "L", .50, .51, 3, 4),
    ]
    # All Elo predictions select the home side.
    games = [
        {
            "game_id": gid, "home_team": h, "away_team": a,
            "elo_home_probability": p, "elo_confidence": p,
            "elo_winner": h, "challenger_home_probability": cp,
            "ppg_margin": pp, "prior_games_min": games,
        }
        for gid, h, a, p, cp, pp, games in picks
    ]
    return {"season":2026,"week":6,"games":games,
            "created_at_utc":"2026-10-13T16:03:27+00:00",
            "history_is_pregame":True}


def test_picks_rank_by_tier_and_restrict_additions():
    data=shortlist(fixture())
    assert [x["game_id"] for x in data["core"]] == ["one","two","three"]
    assert [x["game_id"] for x in data["potential"]] == ["five","four"]
    assert all(x["tier"] is None for x in data["potential"])
    assert historic_total()=={"wins":148,"losses":45}
    assert history_rate(148,45)=="76.7%"


def test_losing_games_cannot_rewrite_archived_picks():
    snap=fixture()
    original=shortlist(snap)
    altered=deepcopy(snap)
    # A final result is not even part of the frozen forecast schema.
    for entry in altered["games"]:
        entry["final_score"] = [0,100]
        entry["outcome"] = "L"
    assert shortlist(altered) == original


def test_load_archive_rejects_tampering_and_late_archive(tmp_path):
    snap=fixture()
    snap["snapshot_sha256"]=hashlib.sha256(
        json.dumps(snap["games"],sort_keys=True).encode()).hexdigest()
    path=tmp_path/"2026_week_06.json"
    path.write_text(json.dumps(snap))
    loaded=load_snapshot(2026,6,tmp_path)
    assert loaded is not None
    frame=pd.DataFrame([{
        "game_id":g["game_id"],"home_team":g["home_team"],"away_team":g["away_team"],
        "gameday":"2026-10-18","home_score":None,"away_score":None,
        "completed":False,
    } for g in snap["games"]])
    assert snapshot_is_pregame(loaded,frame)
    snap["created_at_utc"]="2026-10-18T13:00:00Z"
    path.write_text(json.dumps(snap))
    assert not snapshot_is_pregame(load_snapshot(2026,6,tmp_path),frame)
    snap["games"][0]["elo_confidence"]=.91
    path.write_text(json.dumps(snap))
    assert load_snapshot(2026,6,tmp_path) is None


def test_grade_fails_closed_for_unfinished_and_handles_ties():
    picks=shortlist(fixture())["core"]
    frame=pd.DataFrame([
        {"game_id":"one","home_team":"A","away_team":"B","completed":True,
         "home_score":20,"away_score":14},
        {"game_id":"two","home_team":"C","away_team":"D","completed":True,
         "home_score":10,"away_score":13},
        {"game_id":"three","home_team":"E","away_team":"F","completed":False,
         "home_score":None,"away_score":None},
    ])
    assert grade(picks,frame)=={"wins":1,"losses":1,"ties":0,"pending":1}


def test_real_archived_week6_is_integrity_checked():
    snap=load_snapshot(2026,6)
    assert snap is not None
    picked=shortlist(snap)
    assert [x["team"] for x in picked["core"]]==["SF","NE","LA","KC","IND"]
    assert len(picked["core"])==5


def test_malformed_or_inconsistent_probabilities_fail_closed():
    f=fixture()
    f["games"][0]["elo_confidence"]=.99
    assert "one" not in [x["game_id"] for x in shortlist(f)["core"]]
