"""Regression checks for the research-only Home Field Advantage watch flag."""
from __future__ import annotations
import copy
import pandas as pd
import pytest

from sunday_slate import watch
from sunday_slate.ui import game_card
from sunday_slate.metrics import with_kickoffs


def _fixture():
    """16 teams, three completely known weeks plus an upcoming fourth week."""
    teams = [f"T{i:02d}" for i in range(16)]
    games, boxes = [], []
    # Three unique round-robin rounds, so every team has three prior games.
    for week in range(1, 4):
        for i in range(8):
            home, away = teams[i], teams[8 + ((i + week - 1) % 8)]
            gid = f"2026_{week:02d}_{away}_{home}"
            games.append(dict(game_id=gid,season=2026,week=week,game_type="REG",
                 home_team=home,away_team=away,home_score=24 + i,away_score=14 + i,
                 location="Home",gameday="2026-09-06",gametime="13:00"))
            for team, opponent in ((home, away), (away, home)):
                seed=int(team[1:])
                boxes.append(dict(season=2026,week=week,game_id=gid,
                     season_type="REG",team=team,opponent_team=opponent,
                     passing_epa=seed*0.8 + week*0.4,
                     rushing_epa=(16-seed)*0.7 + week*0.1,
                     attempts=21+seed, carries=12+(seed % 8),
                     rushing_yards=49 + seed*13 + week,
                     completions=12 + seed//2,
                     passing_interceptions=seed%4,
                     fumbles_lost_total=(seed+week)%3,
                     passing_20=1+(seed%5),rushing_10=seed%4))
    games.append(dict(game_id="2026_04_T08_T00",season=2026,week=4,game_type="REG",
        home_team="T00",away_team="T08",home_score=None,away_score=None,
        location="Home",gameday="2026-09-27",gametime="13:00",
        home_moneyline=None,away_moneyline=None))
    return pd.DataFrame(games),pd.DataFrame(boxes)


def test_previous_week_complete_stat_profiles_formed():
    games, stats = _fixture()
    ratings = watch._profiles(games, stats, 2026, 4)
    assert len(ratings) == 16
    assert all(len(x) == 2 for x in ratings.values())


def test_magnitude_thresholds_and_odds_independent(monkeypatch):
    games, stats = _fixture()
    def profile(magnitude):
        return {"T00":[1.0+magnitude,2.0], "T08":[1.,1.]}
    monkeypatch.setattr(watch,"_profiles",lambda *args:profile(.25))
    match=watch.game_watch_flags(games,stats,2026,4)
    assert match["2026_04_T08_T00"]["magnitude"] == pytest.approx(.25)
    assert match["2026_04_T08_T00"]["team"]=="T00"
    # A missing moneyline is permitted: this is a statistical watch flag.
    assert pd.isna(games.iloc[-1]["home_moneyline"])
    monkeypatch.setattr(watch,"_profiles",lambda *args:profile(.4999))
    assert len(watch.game_watch_flags(games,stats,2026,4))==1
    monkeypatch.setattr(watch,"_profiles",lambda *args:profile(.5))
    assert watch.game_watch_flags(games,stats,2026,4)=={}
    monkeypatch.setattr(watch,"_profiles",lambda *args:profile(.2499))
    assert watch.game_watch_flags(games,stats,2026,4)=={}


def test_neutral_site_not_flagged_and_missing_data_fails_closed(monkeypatch):
    games, stats = _fixture()
    monkeypatch.setattr(watch,"_profiles",lambda *args:{"T00":[1.3,2.], "T08":[1.,1.]})
    games.loc[games.week.eq(4),"location"]="Neutral"
    assert watch.game_watch_flags(games,stats,2026,4)=={}
    games.loc[games.week.eq(4),"location"]=None
    assert watch.game_watch_flags(games,stats,2026,4)=={}
    assert watch.game_watch_flags(games,stats.drop(columns=["passing_20"]),2026,4)=={}


def test_same_week_final_scores_and_stats_cannot_change_pregame_profiles():
    games,stats=_fixture()
    original=watch._profiles(games,stats,2026,4)
    modified=games.copy()
    modified.loc[modified.week.eq(4),["home_score","away_score"]]=[300,0]
    future=stats.iloc[:1].copy()
    future["week"]=4
    future["passing_epa"]=9e10
    future["rushing_epa"]=9e10
    augmented=pd.concat([stats,future],ignore_index=True)
    after=watch._profiles(modified,augmented,2026,4)
    assert original.keys()==after.keys()
    for team in original:
        assert original[team].tolist()==after[team].tolist()


def test_missing_previous_team_box_excludes_team_without_invented_stats():
    games, stats=_fixture()
    row=stats[(stats.team=="T00")&(stats.week==2)].index
    assert len(row)==1
    incomplete=stats.drop(index=row)
    profiles=watch._profiles(games,incomplete,2026,4)
    assert "T00" not in profiles
    assert watch.game_watch_flags(games,incomplete,2026,4)=={}


def test_card_highlight_is_visible_and_is_not_recommendation():
    games,_=_fixture()
    card=with_kickoffs(games.iloc[-1:].copy()).iloc[0]
    watch_info={"team":"T00","magnitude":.4867,
                "offense_edge":.4867,"defense_edge":1.8092}
    normal=game_card(card,{}, {})
    flagged=game_card(card,{}, {},watch=watch_info)
    assert "GAME TO WATCH" not in normal
    assert 'class="ss-match ss-watch"' in flagged
    assert "★ GAME TO WATCH" in flagged
    assert "Magnitude 0.49" in flagged
    assert "not a tier, betting recommendation, or change to Elo" in flagged
    assert "<article" in flagged and "</article>" in flagged
    escaped=game_card(card,{"T00":{"name":"<script>bad</script>"}},{},watch=watch_info)
    assert "&lt;script&gt;" in escaped and "<script>bad</script>" not in escaped
