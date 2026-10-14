"""Persist and compare book-specific, timestamped pregame line observations.

The first captured quote is NOT necessarily the sportsbook opening line.
The public history contains prices, never API credentials or customer data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import math
from urllib.request import Request, urlopen

import pandas as pd

HISTORY_URL = ("https://raw.githubusercontent.com/"
               "christianmellis1-debug/Sunday-slate/line-history/data/line_history.json")
FIELDS = ("home_spread", "away_spread", "home_moneyline", "away_moneyline")
MAX_SNAPSHOTS = 180


def game_key(game) -> str | None:
    """Stable source-independent matchup identity. Kickoff must include a timezone."""
    try:
        kickoff = pd.Timestamp(game["kickoff_ct"])
        if pd.isna(kickoff) or kickoff.tzinfo is None:
            return None
        home, away = str(game["home_team"]), str(game["away_team"])
        if not home or not away or home == away:
            return None
        season = int(game["season"])
        return f"{season}|{away}|{home}|{kickoff.tz_convert('UTC').strftime('%Y-%m-%dT%H:%MZ')}"
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _valid(value, spread: bool):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    if spread:
        return number if abs(number) <= 30 and number * 2 == int(number * 2) else None
    return int(number) if number == int(number) and (number <= -100 or number >= 100) else None


def capture(history: dict, game, quote: dict, *, captured_at: str) -> bool:
    """Record a change only when the quote differs; preserve first and last observation times."""
    key = game_key(game)
    if key is None or not isinstance(quote, dict) or quote.get("source") != "DraftKings":
        return False
    if bool(game.get("completed")):
        return False
    try:
        timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        kickoff = pd.Timestamp(game["kickoff_ct"])
        if timestamp.tzinfo is None or pd.Timestamp(timestamp) >= kickoff:
            return False
    except (ValueError, TypeError):
        return False

    prices = {field: _valid(quote.get(field), field.endswith("_spread")) for field in FIELDS}
    if all(v is None for v in prices.values()):
        return False
    # Do not record disjoint two-sided spreads as if they were valid.
    h, a = prices["home_spread"], prices["away_spread"]
    if h is None or a is None or abs(h + a) > .001:
        prices["home_spread"] = prices["away_spread"] = None

    games = history.setdefault("games", {})
    record = games.setdefault(key, {"books": {}})
    book = record.setdefault("books", {}).setdefault("DraftKings", {
        "source_feed": "ESPN", "first_seen": captured_at, "last_seen": captured_at,
        "snapshots": [],
    })
    observations = book.setdefault("snapshots", [])
    if observations and observations[-1].get("at", "") > captured_at:
        return False
    changed = not observations or any(observations[-1].get(field) != prices[field] for field in FIELDS)
    if changed:
        observations.append({"at": captured_at, **prices})
        if len(observations) > MAX_SNAPSHOTS:
            # Retain the first observed quote when pruning intermediates.
            book["snapshots"] = [observations[0]] + observations[-(MAX_SNAPSHOTS - 1):]
    book["last_seen"] = captured_at
    history["updated_at"] = captured_at
    return changed


def load_history(timeout: int = 5) -> dict:
    try:
        req = Request(HISTORY_URL, headers={"Accept": "application/json", "User-Agent": "SundaySlate/1.0"})
        with urlopen(req, timeout=timeout) as response:
            content = response.read(8_000_000)
        data = json.loads(content)
        if data.get("schema_version") == 1 and isinstance(data.get("games"), dict):
            return data
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return {"schema_version": 1, "games": {}}


def change_for_game(history: dict, game, current_quote: dict | None = None) -> dict | None:
    """Compare same-book quotes; use ESPN live quote only with ESPN-captured history.

    If the current card shows TheRundown, avoid silently mixing feeds:
    history-to-history ESPN movement is returned with its own timestamps.
    """
    key = game_key(game)
    data = (history.get("games", {}).get(key, {}).get("books", {}).get("DraftKings", {})
            if key and isinstance(history, dict) else {})
    observations = data.get("snapshots", [])
    if not observations:
        return None
    first, last = observations[0], observations[-1]
    latest = last
    if (current_quote and current_quote.get("source") == "DraftKings"
            and current_quote.get("feed") == "ESPN"):
        prices = {field: _valid(current_quote.get(field), field.endswith("_spread")) for field in FIELDS}
        if prices["home_spread"] is None or prices["away_spread"] is None or abs(prices["home_spread"] + prices["away_spread"]) > .001:
            prices["home_spread"] = prices["away_spread"] = None
        latest = {**prices, "at": current_quote.get("fetched_at") or data.get("last_seen")}
    return {"first": first, "latest": latest, "last_checked": data.get("last_seen"),
            "feed": data.get("source_feed", "ESPN"), "observations": len(observations)}


def _spread(value):
    return "—" if value is None else f"{float(value):+g}"


def _moneyline(value):
    return "—" if value is None else f"{int(value):+d}"


def render_movement(movement: dict | None, away: str, home: str) -> str:
    """Small change marker and collapsed details; never invent an opening quote."""
    if not movement:
        return ""
    first, latest = movement["first"], movement["latest"]
    rows = []
    spread_delta = None
    for side, team in (("away", away), ("home", home)):
        previous, current = first.get(side + "_spread"), latest.get(side + "_spread")
        if previous is not None and current is not None:
            difference = float(current) - float(previous)
            if side == "home":
                spread_delta = difference
            rows.append(f"<tr><td>{escape(team)} spread</td><td>{_spread(previous)}</td>"
                        f"<td>{_spread(current)}</td><td>{difference:+g} pts</td></tr>")
        previous, current = first.get(side + "_moneyline"), latest.get(side + "_moneyline")
        if previous is not None and current is not None:
            rows.append(f"<tr><td>{escape(team)} ML</td><td>{_moneyline(previous)}</td>"
                        f"<td>{_moneyline(current)}</td><td>{int(current) - int(previous):+d}</td></tr>")
    if not rows:
        return ""
    spread_moved = spread_delta is not None and abs(spread_delta) >= .01
    ml_changed = any(first.get(s+"_moneyline") is not None and latest.get(s+"_moneyline") is not None
                     and first[s+"_moneyline"] != latest[s+"_moneyline"] for s in ("home", "away"))
    if spread_moved:
        chip = f'<div class="ss-line-move">↔ Spread moved {abs(spread_delta):g} pts · {escape(home)} {_spread(first["home_spread"])} → {_spread(latest["home_spread"])}</div>'
    elif ml_changed:
        chip = '<div class="ss-line-move">↔ Moneyline movement detected</div>'
    else:
        chip = ""
    first_at = escape(str(first.get("at") or "unknown"))
    latest_at = escape(str(latest.get("at") or "unknown"))
    last_checked = escape(str(movement.get("last_checked") or "unknown"))
    details = (
        '<details class="ss-card-details"><summary>Line movement · DraftKings</summary>'
        '<table class="ss-odds-table"><thead><tr><th>Market</th><th>First captured</th>'
        '<th>Latest seen</th><th>Change</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table>'
        f'<div class="ss-source-note">ESPN-published DraftKings quotes · First captured: {first_at}'
        f' · Latest quote timestamp: {latest_at} · Last collector check: {last_checked}. '
        'First captured is not necessarily the opening line. Prices may be delayed; '
        'movement is informational and does not modify model picks.</div></details>'
    )
    return chip + details
