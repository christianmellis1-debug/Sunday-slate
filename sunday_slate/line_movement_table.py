"""Readable weekly line movement tables built from saved sportsbook observations.

Only compares DraftKings observations from ESPN; "first" means first captured,
not a verified sportsbook opening line. No changes to model predictions.
"""
from __future__ import annotations

import pandas as pd

from sunday_slate.line_movement import change_for_game
from sunday_slate.market import implied_probability, valid_american


def _spread(value):
    try:
        return f"{float(value):+g}" if value is not None else "—"
    except (TypeError, ValueError, OverflowError):
        return "—"


def _moneyline(value):
    number = valid_american(value)
    return f"{number:+d}" if number is not None else "—"


def _observed_ct(value):
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    return parsed.tz_convert("America/Chicago").strftime("%m/%d %I:%M %p") if pd.notna(parsed) else "—"


def _ml_direction(first, latest):
    a, b = valid_american(first), valid_american(latest)
    if a is None or b is None:
        return "Unavailable"
    before, after = implied_probability(a), implied_probability(b)
    if abs(after - before) < 0.0000001:
        return "Unchanged"
    return "Shortened" if after > before else "Lengthened"


def weekly_tables(slate: pd.DataFrame, history: dict, quotes: dict | None = None):
    """Return spread and ML row tables and a count of games with captured moves.

    The spread is the HOME spread (negative = home favorite); movement toward
    home corresponds to a decreasing home spread. Moneyline changes are
    classified by implied probability to handle +100 / -110 crossings.
    """
    spread_rows, moneyline_rows = [], []
    tracked = moved = 0
    quotes = quotes or {}
    for game in slate.to_dict("records"):
        home, away = str(game["home_team"]), str(game["away_team"])
        matchup = f"{away} @ {home}"
        movement = change_for_game(history, game, quotes.get(str(game["game_id"])))
        first = movement["first"] if movement else {}
        latest = movement["latest"] if movement else {}
        observed = _observed_ct(latest.get("at"))
        if movement:
            tracked += 1
        old_home, new_home = first.get("home_spread"), latest.get("home_spread")
        shift = None if old_home is None or new_home is None else float(new_home) - float(old_home)
        if shift is None:
            spread_direction = "Unavailable"
            spread_shift = "—"
        elif abs(shift) < 0.001:
            spread_direction = "Unchanged"
            spread_shift = "0"
        else:
            spread_direction = f"Toward {home}" if shift < 0 else f"Toward {away}"
            spread_shift = f"{shift:+g}"
        spread_rows.append({
            "Matchup": matchup,
            "Home · first": _spread(old_home),
            "Home · latest": _spread(new_home),
            "Shift (pts)": spread_shift,
            "Direction": spread_direction,
            "Observed (CT)": observed,
            "_changed": shift is not None and abs(shift) >= 0.001,
        })
        game_moved = shift is not None and abs(shift) >= 0.001
        for team, side in ((away, "away"), (home, "home")):
            old_ml, new_ml = first.get(side + "_moneyline"), latest.get(side + "_moneyline")
            direction = _ml_direction(old_ml, new_ml)
            if direction in ("Shortened", "Lengthened"):
                game_moved = True
            moneyline_rows.append({
                "Matchup": matchup,
                "Team": team,
                "ML · first": _moneyline(old_ml),
                "ML · latest": _moneyline(new_ml),
                "Movement": direction,
                "Observed (CT)": observed,
                "_changed": direction in ("Shortened", "Lengthened"),
            })
        if game_moved:
            moved += 1
    return pd.DataFrame(spread_rows), pd.DataFrame(moneyline_rows), tracked, moved
