import math

import pandas as pd
import pytest

from sunday_slate.market import (
    valid_american, implied_probability, profit_per_unit,
    analyze_moneyline, screen_side, historical_screen, historical_report,
)
from sunday_slate.matchup import team_advanced_profiles, qb_recent_profiles, matchup_research
from sunday_slate.ui import matchup_panel, market_panel, injury_panel
from sunday_slate.injuries import reported_injuries


def market_schedules():
    return pd.DataFrame([
        dict(game_id="2024_01_B_A", season=2024, week=1, home_team="A", away_team="B",
             home_score=28, away_score=24, home_moneyline=140, away_moneyline=-165),
        dict(game_id="2024_02_B_A", season=2024, week=2, home_team="A", away_team="B",
             home_score=10, away_score=24, home_moneyline=-110, away_moneyline=-110),
        dict(game_id="2024_03_B_A", season=2024, week=3, home_team="A", away_team="B",
             home_score=7, away_score=7, home_moneyline=-110, away_moneyline=-110),
        dict(game_id="2024_04_B_A", season=2024, week=4, home_team="A", away_team="B",
             home_score=None, away_score=None, home_moneyline=-110, away_moneyline=-110),
    ])


def projections():
    return pd.DataFrame([
        dict(game_id="2024_01_B_A", season=2024, home_probability=0.72, pick_result="Correct"),
        dict(game_id="2024_02_B_A", season=2024, home_probability=0.72, pick_result="Incorrect"),
        dict(game_id="2024_03_B_A", season=2024, home_probability=0.72, pick_result="Push"),
        dict(game_id="2024_04_B_A", season=2024, home_probability=0.72, pick_result="Pending"),
    ])


def test_american_odds_and_profit_math():
    assert valid_american(-100) == -100
    assert valid_american(100) == 100
    for val in (None, False, True, "—", -99, 0, 99, float("inf"), float("nan")):
        assert valid_american(val) is None
    assert implied_probability(-150) == pytest.approx(.60)
    assert implied_probability(150) == pytest.approx(.40)
    assert profit_per_unit(-150) == pytest.approx(2/3)
    assert profit_per_unit(150) == pytest.approx(1.5)


def test_normalized_market_and_strict_failure_modes():
    m = analyze_moneyline(0.60, -110, -110)
    assert m["sides"]["home"]["no_vig"] == pytest.approx(.5)
    assert m["sides"]["away"]["edge"] == pytest.approx(-.1)
    assert screen_side(m) == "home"
    assert analyze_moneyline(0.6, -110, None) is None
    assert analyze_moneyline(float("nan"), -110, -110) is None
    assert analyze_moneyline(0.60, -1000, -1000) is None
    assert screen_side(analyze_moneyline(.5, -110, -110)) is None


def test_reference_roi_never_includes_unplayed_or_tied_games():
    out = historical_screen(market_schedules(), projections(), seasons=(2024,))
    assert len(out) == 2
    assert set(out.game_id) == {"2024_01_B_A","2024_02_B_A"}
    assert all(out.result.isin(["Win","Loss"]))
    report = historical_report(out)
    assert report["bets"] == 2 and report["wins"] == 1 and report["losses"] == 1
    assert math.isfinite(report["roi"])


def test_missing_moneyline_fields_fail_closed():
    frame = market_schedules().drop(columns="away_moneyline")
    assert historical_screen(frame, projections()).empty


def weekly_teams():
    return pd.DataFrame([
        dict(season=2026, week=1, season_type="REG", game_id="g1", team="A", opponent_team="B",
             passing_epa=6., attempts=30, rushing_epa=3., carries=15, passing_cpoe=2.),
        dict(season=2026, week=1, season_type="REG", game_id="g1", team="B", opponent_team="A",
             passing_epa=-6., attempts=20, rushing_epa=-1., carries=20, passing_cpoe=-2.),
        dict(season=2026, week=2, season_type="REG", game_id="g2", team="A", opponent_team="B",
             passing_epa=1000., attempts=25, rushing_epa=1000., carries=20, passing_cpoe=99.),
        dict(season=2026, week=2, season_type="REG", game_id="g2", team="B", opponent_team="A",
             passing_epa=1000., attempts=25, rushing_epa=1000., carries=20, passing_cpoe=99.),
    ])


def test_advanced_matchups_are_prior_week_only_and_two_sided():
    p = team_advanced_profiles(weekly_teams(), 2026, 2)
    assert p["A"]["pass_epa_per_att"] == pytest.approx(.2)
    assert p["B"]["pass_epa_per_att"] == pytest.approx(-.3)
    assert p["A"]["pass_epa_allowed_per_att"] == pytest.approx(-.3)
    assert p["B"]["pass_epa_allowed_per_att"] == pytest.approx(.2)
    assert p["A"]["rush_epa_allowed_per_carry"] == pytest.approx(-.05)
    assert p["A"]["pass_cpoe"] == pytest.approx(2.)
    assert team_advanced_profiles(weekly_teams(), 2026, 1) == {}


def test_qb_profile_most_used_not_future_starter():
    qb = pd.DataFrame([
        dict(season=2026, week=1, season_type="REG", game_id="g1", team="A", position="QB", player_display_name="John QB", attempts=22, passing_yards=210, passing_interceptions=1),
        dict(season=2026, week=1, season_type="REG", game_id="g1", team="A", position="QB", player_display_name="Backup QB", attempts=3, passing_yards=22, passing_interceptions=0),
        dict(season=2026, week=2, season_type="REG", game_id="g2", team="A", position="QB", player_display_name="Backup QB", attempts=500, passing_yards=5000, passing_interceptions=0),
    ])
    q = qb_recent_profiles(qb, 2026, 2)["A"]
    assert q["name"] == "John QB"
    assert q["yards_per_attempt"] == pytest.approx(210 / 22, abs=.01)
    assert "not a confirmed starter" in q["label"]
    assert "John QB" in matchup_panel("A", "B", matchup_research("A", "B", {}, {"A": q}))


def test_panels_escape_team_and_player_text():
    markup = market_panel("<img src=x>", "B", analyze_moneyline(.65, 120, -140), True)
    assert "<img src=x>" not in markup
    assert "&lt;img" in markup
    assert "not confirmed current DraftKings" in markup or "not confirmed current DraftKings" in markup


def test_injury_snapshot_uses_only_same_week_and_pre_kickoff():
    frame = pd.DataFrame([
        dict(season=2026, week=5, team="DAL", full_name="Joe RB", report_status="Out", date_modified="2026-10-03T15:00:00Z"),
        dict(season=2026, week=6, team="DAL", full_name="Joe RB", report_status="Questionable", date_modified="2026-10-10T15:00:00Z"),
        dict(season=2026, week=6, team="DAL", full_name="Joe RB", report_status="Out", date_modified="2026-10-11T13:00:00Z"),
        dict(season=2026, week=6, team="PHI", full_name="<b>Q</b>", report_status="Doubtful", date_modified="2026-10-10T15:00:00Z"),
        dict(season=2026, week=6, team="PHI", full_name="No Status", report_status="", date_modified="2026-10-10T15:00:00Z"),
    ])
    kickoff = pd.Timestamp("2026-10-11T12:00:00Z")
    result = reported_injuries(frame, 2026, 6, kickoff, ("DAL", "PHI"))
    assert len(result["DAL"]) == 1 and result["DAL"][0]["status"] == "Questionable"
    assert len(result["PHI"]) == 1
    html = injury_panel("DAL", "PHI", result)
    assert "<b>Q</b>" not in html and "&lt;b&gt;Q&lt;/b&gt;" in html
    assert "not a healthy designation" in html or "Not included in model" in html


def test_missing_injury_data_cannot_mark_teams_healthy():
    output = reported_injuries(None, 2026, 6, "2026-10-11T12:00:00Z", ("DAL", "PHI"))
    assert output == {"DAL": [], "PHI": []}
    rendered = injury_panel("DAL", "PHI", output, source_available=False)
    assert "unavailable" in rendered and "not be treated as healthy" in rendered
