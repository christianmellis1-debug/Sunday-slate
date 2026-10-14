"""Offline regression coverage: source fidelity, identities and movement direction."""
import pandas as pd

from sunday_slate.line_movement import capture, change_for_game, game_key, render_movement


def fixture():
    return dict(season=2026, game_id="2026_07_SEA_DEN", away_team="SEA",
                home_team="DEN", kickoff_ct=pd.Timestamp("2026-12-01T01:00:00Z"),
                completed=False)


def quote(home=-3.5, away=3.5, home_ml=-175, away_ml=150, feed="ESPN"):
    return dict(source="DraftKings", feed=feed, home_spread=home, away_spread=away,
                home_moneyline=home_ml, away_moneyline=away_ml,
                fetched_at="2026-11-01T13:00:00Z")


def test_capture_retains_first_and_only_new_price_events():
    game = fixture()
    archive = {"schema_version": 1, "games": {}}
    assert capture(archive, game, quote(), captured_at="2026-10-14T14:00:00Z")
    assert not capture(archive, game, quote(), captured_at="2026-10-14T17:00:00Z")
    assert capture(archive, game, quote(home=-2, away=2, home_ml=-130, away_ml=115),
                   captured_at="2026-10-15T14:00:00Z")
    movement = change_for_game(archive, game)
    assert movement["first"]["home_spread"] == -3.5
    assert movement["latest"]["home_spread"] == -2
    assert movement["observations"] == 2
    assert "1.5 pts" in render_movement(movement, "SEA", "DEN")
    assert "First captured is not necessarily the opening line" in render_movement(movement, "SEA", "DEN")


def test_do_not_mix_different_feeds_in_realtime():
    game = fixture()
    archive = {"schema_version": 1, "games": {}}
    capture(archive, game, quote(), captured_at="2026-10-14T14:00:00Z")
    assert change_for_game(archive, game, quote(-7, 7, feed="TheRundown"))["latest"]["home_spread"] == -3.5
    assert change_for_game(archive, game, quote(-2, 2, feed="ESPN"))["latest"]["home_spread"] == -2


def test_reject_wrong_book_completed_and_after_kickoff():
    game = fixture()
    archive = {"schema_version": 1, "games": {}}
    other = {**quote(), "source": "FanDuel"}
    assert not capture(archive, game, other, captured_at="2026-10-14T14:00:00Z")
    assert not capture(archive, {**game, "completed": True}, quote(), captured_at="2026-10-14T14:00:00Z")
    assert not capture(archive, game, quote(), captured_at="2026-12-02T14:00:00Z")
    assert not archive["games"]


def test_key_matching_requires_timezone_and_uses_team_identity():
    game = fixture()
    key = game_key(game)
    assert key.startswith("2026|SEA|DEN|")
    assert key != game_key({**game, "home_team": "DAL"})
    assert game_key({**game, "kickoff_ct": pd.Timestamp("2026-12-01 01:00:00")}) is None
