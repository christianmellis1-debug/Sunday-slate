"""Book-specific NFL pregame odds via TheRundown: DraftKings 19, FanDuel 23.

Each quote is isolated to the requested book. No reference-odds fallback.
"""
import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

class DKFeedError(RuntimeError):
    pass

NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints",
    "NYG": "New York Giants", "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}
def _norm(v):
    return re.sub(r"[^a-z0-9]", "", str(v).lower())

ALIASES = {_norm(name): abbr for abbr, name in NAMES.items()}
ALIASES.update({_norm(abbr): abbr for abbr in NAMES})
ALIASES.update({_norm(name.split()[-1]): abbr for abbr, name in NAMES.items()})
ALIASES.update({"washingtonfootballteam": "WAS", "jacksonvillejags": "JAX",
                "larams": "LAR", "lachargers": "LAC"})

def _team(name):
    return ALIASES.get(_norm(name))

def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) and n != .0001 else None
    except (TypeError, ValueError, OverflowError):
        return None

def _spread_value(line):
    for key in ("value", "line", "points", "point"):
        val = line.get(key)
        if isinstance(val, (float, int)):
            return _number(val)
        if isinstance(val, str):
            # TheRundown uses e.g. "-3.5"; allow a team-label prefix.
            match = re.fullmatch(r"(?:[A-Za-z][A-Za-z .]*\s+)?([+-]?\d+(?:\.\d+)?)", val.strip())
            if match:
                return _number(match.group(1))
    return None

BOOKS = {"DraftKings": "19", "FanDuel": "23"}

def parse_event(event, book="DraftKings"):
    """Return one book-specific event; missing/ambiguous sides fail closed."""
    affiliate = BOOKS[book]
    if not isinstance(event, dict):
        return None
    teams = event.get("teams")
    if not isinstance(teams, list):
        return None
    homes = [_team(t.get("name")) for t in teams
             if isinstance(t, dict) and t.get("is_away") is False]
    aways = [_team(t.get("name")) for t in teams
             if isinstance(t, dict) and t.get("is_away") is True]
    if len(homes) != 1 or len(aways) != 1 or not homes[0] or not aways[0] or homes[0] == aways[0]:
        return None
    home, away = homes[0], aways[0]
    spreads, mls, updates = {}, {}, []
    for market in event.get("markets") or []:
        if not isinstance(market, dict):
            continue
        try:
            market_id = int(market.get("market_id"))
        except (ValueError, TypeError):
            continue
        if market_id not in (1, 2):
            continue
        for participant in market.get("participants") or []:
            if not isinstance(participant, dict):
                continue
            team = _team(participant.get("name"))
            if team not in (home, away):
                continue
            lines = participant.get("lines") or []
            if len(lines) != 1 or not isinstance(lines[0], dict):
                continue
            line = lines[0]
            if line.get("is_main_line") is False or line.get("closed_at"):
                continue
            dk = (line.get("prices") or {}).get(affiliate)
            if not isinstance(dk, dict):
                continue
            price = _number(dk.get("price"))
            if price is None:
                continue
            if dk.get("updated_at"):
                updates.append(str(dk["updated_at"]))
            if market_id == 1:
                if price == int(price) and (price <= -100 or price >= 100):
                    mls[team] = int(price)
            else:
                points = _spread_value(line)
                if points is not None and abs(points) <= 30 and abs(points) * 2 == int(abs(points) * 2):
                    spreads[team] = points
    hs, aw = spreads.get(home), spreads.get(away)
    if hs is None or aw is None or abs(hs + aw) > .001:
        hs = aw = None
    return {"source": book, "home": home, "away": away,
            "home_spread": hs, "away_spread": aw,
            "home_moneyline": mls.get(home), "away_moneyline": mls.get(away),
            "updated_at": max(updates) if updates else None}

def fetch_date(day, key, include_fanduel=False):
    if not key or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise DKFeedError("DK feed not configured")
    params = urlencode({"market_ids": "1,2", "affiliate_ids": "19,23" if include_fanduel else "19",
                        "main_line": "true", "hide_closed": "true"})
    url = f"https://therundown.io/api/v2/sports/2/events/{day}?{params}"
    req = Request(url, headers={"X-TheRundown-Key": key, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=12) as response:
            data = json.load(response)
    except Exception as exc:
        raise DKFeedError("DraftKings prices unavailable") from exc
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise DKFeedError("Malformed DraftKings feed")
    return data

def utc_dates(slate, now=None):
    if slate is None or slate.empty or "kickoff_ct" not in slate:
        return []
    now = pd.Timestamp(now or datetime.now(timezone.utc)).tz_convert("UTC")
    dates = set()
    for r in slate.to_dict("records"):
        if r.get("completed") or pd.isna(r.get("kickoff_ct")):
            continue
        kickoff = pd.Timestamp(r["kickoff_ct"])
        if kickoff.tzinfo and kickoff > now:
            dates.add(kickoff.tz_convert("UTC").strftime("%Y-%m-%d"))
    return sorted(dates)[:5]

def match_games(slate, snapshots, book="DraftKings"):
    if slate is None or slate.empty or "kickoff_ct" not in slate:
        return {}
    keyed = {}
    for day, payload in snapshots.items():
        for event in payload.get("events") or []:
            quote = parse_event(event, book)
            if quote is None:
                continue
            event_day = str(event.get("event_date") or day)[:10]
            key = (event_day, quote["away"], quote["home"])
            keyed[key] = None if key in keyed else quote
    output = {}
    for g in slate.to_dict("records"):
        if g.get("completed") or pd.isna(g.get("kickoff_ct")):
            continue
        kickoff = pd.Timestamp(g["kickoff_ct"])
        if kickoff.tzinfo is None:
            continue
        day = kickoff.tz_convert("UTC").strftime("%Y-%m-%d")
        key = (day, str(g.get("away_team")), str(g.get("home_team")))
        quote = keyed.get(key)
        if quote:
            output[str(g["game_id"])] = quote
    return output
