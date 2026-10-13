"""DraftKings only: verify spread sign, coaching buckets, and no fallback."""
from datetime import datetime, timezone
import pandas as pd
import pytest

from sunday_slate.draftkings import parse_event, match_games, utc_dates
from sunday_slate.coach_flags import coaching_flags, ben_johnson_flags
from sunday_slate.metrics import with_kickoffs
from sunday_slate.ui import game_card

def event(home="Dallas Cowboys", away="New York Giants", favored=3.0,
          book="19", include_away=True):
    def line(value, price=-110):
        return {"value": value, "prices": {book: {
            "price": price, "updated_at": "2026-10-16T18:00:00Z"
        }}}
    participants = [{"name": home, "lines": [line(-favored)]}]
    if include_away:
        participants.append({"name": away, "lines": [line(favored)]})
    return {
        "event_date": "2026-10-18T17:00:00Z",
        "teams": [{"name": away, "is_away": True},
                  {"name": home, "is_away": False}],
        "markets": [
            {"market_id": 2, "participants": participants},
            {"market_id": 1, "participants": [
                {"name": home, "lines": [line(0, -140)]},
                {"name": away, "lines": [line(0, 120)]},
            ]},
        ],
    }

def game(home="DAL", away="NYG", season=2026, week=6, coach="Brian Schottenheimer",
         completed=False, reference_line=18.5):
    return {"game_id": f"{season}_{week:02d}_{away}_{home}",
            "season": season, "week": week, "game_type": "REG",
            "home_team": home, "away_team": away,
            "home_coach": coach, "gameday": "2026-10-18",
            "gametime": "13:00", "location": "Home",
            "home_score": 24 if completed else None,
            "away_score": 17 if completed else None,
            "spread_line": reference_line}

def quote(fav=3, team="home", source="DraftKings"):
    home_spread = -fav if team == "home" else fav
    return {"source": source, "home_spread": home_spread,
            "away_spread": -home_spread, "updated_at": "2026-10-16T18:00:00Z"}

def markers(game_data, dk):
    df = with_kickoffs(pd.DataFrame([game_data]))
    return coaching_flags(df, game_data["season"], game_data["week"],
                          {game_data["game_id"]: dk})

def test_draftkings_price_and_sign_extracted():
    data = parse_event(event())
    assert data["source"] == "DraftKings"
    assert data["home_spread"] == -3 and data["away_spread"] == 3
    assert data["home_moneyline"] == -140
    assert data["away_moneyline"] == 120
    assert parse_event(event(book="23"))["home_spread"] is None
    assert parse_event(event(book="23"))["home_moneyline"] is None
    assert parse_event(event(include_away=False))["home_spread"] is None

def test_exact_game_match_never_falls_back_to_nflverse():
    row = game()
    df = with_kickoffs(pd.DataFrame([row]))
    dates = utc_dates(df, now=datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert dates == ["2026-10-18"]
    quotes = match_games(df, {dates[0]: {"events": [event()]}})
    assert quotes[row["game_id"]]["home_spread"] == -3
    non_dk = match_games(df, {dates[0]: {"events": [event(book="23")]}})
    assert coaching_flags(df, 2026, 6, non_dk) == {}
    assert coaching_flags(df, 2026, 6, {}) == {}
    assert coaching_flags(df, 2026, 6, None) == {}

@pytest.mark.parametrize("points", [0.5, 1.5, 3.0, 3.5, 7, 9.5])
def test_schottenheimer_is_any_favorite(points):
    row = game()
    found = markers(row, quote(points))
    assert found[row["game_id"]][0]["name"] == "SCHOTTENHEIMER FAVORITE"
    assert markers(row, quote(points, source="nflverse")) == {}
    assert markers(row, quote(points, team="away")) == {}

def test_stefanski_midrange_boundaries():
    row = game(home="ATL", away="BAL", coach="Kevin Stefanski")
    for points in (3.5, 5, 7):
        result = markers(row, quote(points))
        assert result[row["game_id"]][0]["name"] == "STEFANSKI MID-RANGE FAVORITE"
    for points in (0, 3, 7.5):
        assert markers(row, quote(points)) == {}
    cle = game(home="CLE", away="BAL", season=2025, coach="Kevin Stefanski")
    assert markers(cle, quote(4.5))[cle["game_id"]][0]["name"] == "STEFANSKI MID-RANGE FAVORITE"

def test_ben_johnson_only_small_favorite_and_dk():
    row = game(home="CHI", away="NYJ", coach="Ben Johnson")
    df = with_kickoffs(pd.DataFrame([row]))
    gid = row["game_id"]
    assert ben_johnson_flags(df, 2026, 6) == {}
    for points in (0.5, 2.5, 3):
        assert ben_johnson_flags(df, 2026, 6, {gid: quote(points)})[gid]["name"] == "BEN JOHNSON SPECIAL"
    assert ben_johnson_flags(df, 2026, 6, {gid: quote(3.5)}) == {}
    found = markers(row, quote(3))
    html = game_card(df.iloc[0], {}, {}, coaching=found[gid], dk_quote=quote(3))
    assert "BEN JOHNSON SPECIAL" in html and "DraftKings" in html

def test_wrong_coach_completed_games_and_outside_tenure():
    assert markers(game(coach="Someone Else"), quote(3)) == {}
    assert markers(game(completed=True), quote(3)) == {}
    assert markers(game(season=2024), quote(3)) == {}
