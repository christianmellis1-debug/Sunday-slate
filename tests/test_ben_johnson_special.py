"""Legacy Ben Johnson tests now enforce DraftKings-only rule."""
import pandas as pd
from sunday_slate.coach_flags import ben_johnson_flags
from sunday_slate.metrics import with_kickoffs
from sunday_slate.ui import game_card

def test_ben_johnson_fails_closed_without_draftkings():
    row = {"game_id": "2026_06_NYJ_CHI", "season": 2026, "week": 6,
           "game_type": "REG", "home_team": "CHI", "away_team": "NYJ",
           "home_coach": "Ben Johnson", "gameday": "2026-10-18",
           "gametime": "13:00", "location": "Home", "spread_line": 15.5,
           "home_score": None, "away_score": None}
    df = with_kickoffs(pd.DataFrame([row]))
    gid = row["game_id"]
    assert ben_johnson_flags(df, 2026, 6) == {}
    valid = {"source": "DraftKings", "home_spread": -3, "away_spread": 3}
    assert ben_johnson_flags(df, 2026, 6, {gid: valid})[gid]["name"] == "BEN JOHNSON SPECIAL"
    assert ben_johnson_flags(df, 2026, 6, {gid: {"source": "nflverse",
                                                  "home_spread": -3,
                                                  "away_spread": 3}}) == {}
    assert ben_johnson_flags(df, 2026, 6, {gid: {"source": "DraftKings",
                                                  "home_spread": -3.5,
                                                  "away_spread": 3.5}}) == {}
    marker = ben_johnson_flags(df, 2026, 6, {gid: valid})[gid]
    html = game_card(df.iloc[0], {}, {}, ben_johnson=marker)
    assert "BEN JOHNSON SPECIAL" in html
    assert "DraftKings" in html
