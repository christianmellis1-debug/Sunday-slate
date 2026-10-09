from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from sunday_slate.metrics import game_kickoff, with_kickoffs, team_profiles, default_week, time_label, weeks_for, stage_mask
from sunday_slate.ui import game_card, branding_map


def schedule():
    return pd.DataFrame([
        dict(game_id="2026_05_DAL_NO", season=2026, game_type="REG", week=5, gameday="2026-10-04", gametime="13:00", away_team="DAL", home_team="NO", away_score=28, home_score=14),
        dict(game_id="2026_06_DAL_NYG", season=2026, game_type="REG", week=6, gameday="2026-10-11", gametime="13:00", away_team="DAL", home_team="NYG", away_score=None, home_score=None),
        dict(game_id="2026_06_NO_PHI", season=2026, game_type="REG", week=6, gameday="2026-10-12", gametime="20:15", away_team="NO", home_team="PHI", away_score=None, home_score=None),
        dict(game_id="2026_07_DAL_NO", season=2026, game_type="REG", week=7, gameday="2026-10-18", gametime="13:00", away_team="DAL", home_team="NO", away_score=None, home_score=None),
    ])


def stats():
    return pd.DataFrame([
        dict(season=2026, week=5, season_type="REG", team="DAL", passing_yards=290, rushing_yards=130),
        dict(season=2026, week=5, season_type="REG", team="NO", passing_yards=250, rushing_yards=90),
        dict(season=2026, week=6, season_type="REG", team="DAL", passing_yards=9999, rushing_yards=9999),
    ])


def test_eastern_kickoff_converts_to_central():
    assert game_kickoff("2026-10-11", "13:00").hour == 12
    assert time_label(game_kickoff("2026-10-11", "09:30")).endswith("8:30 AM CT")
    assert game_kickoff("2026-12-13", "13:00").hour == 12


def test_nonexistent_dates_fail_closed():
    assert pd.isna(game_kickoff("TBD", "TBD"))


def test_week_navigation_selects_live_week():
    data = with_kickoffs(schedule())
    now = datetime(2026, 10, 9, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert default_week(data, 2026, now) == 6


def test_only_preregular_history_in_profiles():
    p = team_profiles(schedule(), stats(), 2026, week=6)
    assert p["DAL"]["wins"] == 1
    assert p["DAL"]["ppg"] == 28
    assert p["NO"]["opp_ppg"] == 28
    assert p["DAL"]["pass_ypg"] == 290
    assert p["DAL"]["rush_ypg"] == 130


def test_empty_early_week_safely_returns_no_scores():
    p = team_profiles(schedule(), stats(), 2026, week=1)
    assert p == {}


def test_scores_not_mistaken_for_final_when_only_one_score():
    data = schedule()
    data.loc[1, "away_score"] = 12
    assert with_kickoffs(data).loc[1, "completed"] == False


def test_bad_logo_url_is_filtered():
    brands = branding_map(pd.DataFrame([{"team_abbr":"DAL", "team_name":"Dallas Cowboys", "team_logo_espn":"javascript:alert(1)", "team_color":"red"}]))
    assert brands["DAL"]["logo"] is None
    assert brands["DAL"]["color"] == "#364f6b"


def test_card_escapes_untrusted_team_name():
    g = with_kickoffs(schedule()).iloc[1]
    html = game_card(g, {"DAL": {"name": "<img src=x onerror=alert(1)>"}}, {})
    assert '<img src=x onerror=alert(1)>' not in html
    assert '&lt;img' in html
    assert "12:00 PM CT" in html


def test_postseason_grouping_uses_nflverse_round_codes():
    data = schedule()
    extra = pd.DataFrame([
        dict(game_id="2025_19_X_Y", season=2025, game_type="WC", week=19, gameday="2026-01-10", gametime="13:00", away_team="DAL", home_team="NYG", away_score=24, home_score=20),
        dict(game_id="2025_20_X_Y", season=2025, game_type="DIV", week=20, gameday="2026-01-17", gametime="13:00", away_team="NYG", home_team="DAL", away_score=15, home_score=23),
        dict(game_id="2025_22_X_Y", season=2025, game_type="SB", week=22, gameday="2026-02-08", gametime="18:30", away_team="NYG", home_team="DAL", away_score=10, home_score=21),
    ])
    data = pd.concat([data, extra], ignore_index=True)
    assert weeks_for(data, 2025, "POST") == [19, 20, 22]
    assert int(stage_mask(data, "POST").sum()) == 3
    assert int(stage_mask(data, "REG").sum()) == 4
