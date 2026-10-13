"""Ben Johnson Special regression tests: reference spreads only, no model changes."""
import pandas as pd
import pytest

from sunday_slate.coach_flags import ben_johnson_special, ben_johnson_flags
from sunday_slate.metrics import with_kickoffs
from sunday_slate.ui import game_card


def game(season=2026, week=6, home="ATL", away="CHI", spread=-3,
         game_type="REG", **kwargs):
    return dict(season=season, week=week, game_id=f"{season}_{week:02d}_{away}_{home}",
                game_type=game_type, home_team=home, away_team=away,
                spread_line=spread, home_score=None, away_score=None,
                gameday="2026-10-18", gametime="13:00", location="Home", **kwargs)


@pytest.mark.parametrize("spread,expected", [
    (-3.5, False), (-3.0, True), (-2.5, True), (-0.5, True),
    (0.0, False), (1.0, False), (float("nan"), False), (None, False),
])
def test_away_bears_favorite_boundaries(spread, expected):
    assert (ben_johnson_special(game(spread=spread)) is not None) is expected


@pytest.mark.parametrize("spread,expected", [
    (3.5, False), (3.0, True), (0.5, True), (-1.0, False),
])
def test_home_bears_favorite_boundaries(spread, expected):
    assert (ben_johnson_special(game(home="CHI", away="NE", spread=spread)) is not None) is expected


def test_detroit_coordinator_years_and_chicago_coach_years_are_distinct():
    for year in (2022, 2023, 2024):
        match = ben_johnson_special(game(season=year, home="DET", away="GB", spread=2.5))
        assert match and match["role"] == "Offensive coordinator"
        assert ben_johnson_special(game(season=year, home="CHI", away="GB", spread=2.5)) is None
    for year in (2025, 2026):
        match = ben_johnson_special(game(season=year, home="CHI", away="GB", spread=2.5))
        assert match and match["role"] == "Head coach"
        assert ben_johnson_special(game(season=year, home="DET", away="GB", spread=2.5)) is None
    assert ben_johnson_special(game(season=2027, home="CHI", away="GB", spread=2.5)) is None


def test_explicit_different_head_coach_suppresses_flag():
    assert ben_johnson_special(game(home="CHI", away="NE", spread=2.5,
                                    home_coach="Other Coach")) is None
    assert ben_johnson_special(game(home="CHI", away="NE", spread=2.5,
                                    home_coach="Ben Johnson")) is not None


def test_missing_spread_columns_and_playoffs_fail_closed():
    frame = pd.DataFrame([game(spread=-2.5)])
    assert ben_johnson_flags(frame.drop(columns=["spread_line"]), 2026, 6) == {}
    assert ben_johnson_special(game(spread=-2.5, game_type="WC")) is None
    assert ben_johnson_flags(frame, 2026, 6)["2026_06_CHI_ATL"]["favored_by"] == 2.5
    assert ben_johnson_flags(frame, 2026, 7) == {}


def test_card_label_and_watch_flag_can_coexist():
    frame = with_kickoffs(pd.DataFrame([game(home="CHI", away="NE", spread=3.0)]))
    marker = ben_johnson_special(frame.iloc[0].to_dict())
    card = game_card(frame.iloc[0], {}, {}, ben_johnson=marker)
    assert "BEN JOHNSON SPECIAL" in card
    assert "Favored by 3" in card
    assert "not verified live" in card
    assert "BET" not in card  # Research marker, not betting advice
    watch = {"team": "CHI", "magnitude": 0.35}
    card_both = game_card(frame.iloc[0], {}, {}, watch=watch, ben_johnson=marker)
    assert "GAME TO WATCH" in card_both
    assert "BEN JOHNSON SPECIAL" in card_both
