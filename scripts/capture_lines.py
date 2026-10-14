"""Scheduled price-history collection for Sunday Slate.

Run from GitHub Actions after fetching the remote line-history branch.
Tracks ESPN-published DraftKings prices; no paid API or secret is required.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from sunday_slate.draftkings import _team
from sunday_slate.espn_odds import ESPNFeedError, fetch_week, match_quotes
from sunday_slate.line_movement import capture

OUTPUT = Path("/tmp/sunday-slate-lines.json")


def old_history():
    result = subprocess.run(
        ["git", "show", "origin/line-history:data/line_history.json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        try:
            value = json.loads(result.stdout)
            if value.get("schema_version") == 1 and isinstance(value.get("games"), dict):
                return value
        except (ValueError, AttributeError):
            pass
    return {"schema_version": 1, "games": {}}


def fixtures(payload, season):
    """Build fixtures directly from the same ESPN response used for bookmaker quotes."""
    rows = []
    for event in payload.get("events", []):
        for comp in event.get("competitions", []):
            status = comp.get("status", {}).get("type", {})
            if status.get("state") != "pre" or status.get("completed"):
                continue
            opponents = {}
            for side in comp.get("competitors", []):
                team = side.get("team", {})
                opponents[side.get("homeAway")] = (_team(team.get("displayName"))
                                                  or _team(team.get("abbreviation")))
            kickoff = pd.to_datetime(comp.get("date"), utc=True, errors="coerce")
            if pd.isna(kickoff) or not opponents.get("home") or not opponents.get("away"):
                continue
            rows.append(dict(season=season, week=0,
                             game_id=str(event.get("id") or comp.get("id")),
                             home_team=opponents["home"], away_team=opponents["away"],
                             kickoff_ct=kickoff, completed=False))
    return pd.DataFrame(rows, columns=["season", "week", "game_id",
                                       "home_team", "away_team", "kickoff_ct", "completed"])


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    if now.month not in (1, 8, 9, 10, 11, 12):
        print("Outside regular-season collection months; nothing to collect.")
        return 0
    season = now.year if now.month >= 8 else now.year - 1
    history = old_history()
    changes, checked = 0, 0
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    # ESPN generally releases only near-term pregame prices. 18 lightweight calls
    # avoid assumptions about the currently displayed week and include early lines.
    for week in range(1, 19):
        try:
            payload = fetch_week(season, week)
        except ESPNFeedError:
            continue
        games = fixtures(payload, season)
        if games.empty:
            continue
        games = games[games["kickoff_ct"] > pd.Timestamp(now)]
        if games.empty:
            continue
        quotes = match_quotes(games, payload, now=now)["DraftKings"]
        for game in games.to_dict("records"):
            quote = quotes.get(str(game["game_id"]))
            if not quote:
                continue
            checked += 1
            changes += int(capture(history, game, quote, captured_at=stamp))
    if not checked:
        print("No usable pregame DraftKings quotes; preserve existing history.")
        return 0
    # Bound the retained archive to current + previous season, without rewriting past data.
    history["games"] = {k: v for k, v in history.get("games", {}).items()
                        if k.split("|", 1)[0].isdigit() and int(k.split("|", 1)[0]) >= season - 1}
    OUTPUT.write_text(json.dumps(history, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"Checked {checked} game quotes, {changes} prices changed; output={OUTPUT}")
    return checked


if __name__ == "__main__":
    sys.exit(0 if collect() >= 0 else 1)
