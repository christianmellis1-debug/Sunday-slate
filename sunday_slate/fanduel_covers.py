"""FanDuel's published full-game NFL lines via the public Covers comparison page."""
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import re
from bs4 import BeautifulSoup
import pandas as pd
from sunday_slate.draftkings import _number, _team
from sunday_slate.market import valid_american

URL = 'https://www.covers.com/sport/football/nfl/odds'


class CoversFeedError(RuntimeError):
    pass


def fetch_snapshot():
    try:
        with urlopen(Request(URL, headers={'Accept': 'text/html'}), timeout=12) as response:
            html = response.read(6_000_000).decode('utf-8')
        if 'moneyline-table' not in html or 'data-book="FanDuel"' not in html:
            raise ValueError('FanDuel table unavailable')
        return {'html': html, 'fetched_at': datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        raise CoversFeedError('FanDuel via Covers unavailable') from exc


def _text(node):
    return node.get_text(' ', strip=True) if node else ''


def match_quotes(slate, snapshot, now=None):
    """Require exact home/away, Eastern date/time, and a unique full-game row.

    Only the next 14 days are eligible (the page is a rolling current board).
    Market timestamps older than 24 hours are suppressed, not silently refreshed.
    """
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    fetched = pd.to_datetime(snapshot.get('fetched_at'), utc=True, errors='coerce')
    if pd.isna(fetched) or not pd.Timedelta(0) <= now - fetched <= pd.Timedelta(minutes=30):
        return {}
    soup = BeautifulSoup(snapshot.get('html', ''), 'html.parser')
    markets = {}
    for table_id, market in [('moneyline-table', 'moneyline'), ('spread-table', 'spread')]:
        table = soup.find('table', id=table_id)
        if not table:
            continue
        for row in table.select('tr.oddsGameRow'):
            cells = row.select('td[data-book="FanDuel"]')
            if len(cells) != 1:
                continue
            cell = cells[0]
            team = row.select_one('.teams-div')
            if not team:
                continue
            home = _team(_text(team.select_one('.home-cell strong')))
            away = _team(_text(team.select_one('.away-cell strong')))
            aliases = {'JAC': 'JAX', 'LA': 'LAR'}
            home = aliases.get(_text(team.select_one('.home-cell strong')), home)
            away = aliases.get(_text(team.select_one('.away-cell strong')), away)
            label = re.sub(r'\s+', ' ', _text(row.select_one('.game-time')))
            date = re.fullmatch(r'([A-Za-z]{3}) (\d{1,2}), (\d{1,2}):(\d{2})', label)
            if not home or not away or home == away or not date:
                continue
            try:
                updated = pd.to_datetime(float(cell.get('data-date')), unit='s', utc=True)
            except (TypeError, ValueError, OverflowError):
                continue
            if pd.isna(updated) or not pd.Timedelta(0) <= now - updated <= pd.Timedelta(hours=24):
                continue
            values = {}
            for side in ('home', 'away'):
                link = cell.select_one(f'.{side}-cell a.odds-cta')
                if not link or link.get('data-linkcont') != f'odds_click-{market}-fanduel':
                    continue
                if market == 'moneyline':
                    value = valid_american(_text(link.select_one('span.__american')))
                else:
                    raw = ''.join(str(t) for t in link.find_all(string=True, recursive=False)).strip()
                    value = 0.0 if raw.upper() in ('PK', 'PICK') else _number(raw)
                    if value is not None and (abs(value) > 30 or value * 2 != int(value * 2)):
                        value = None
                values[side] = value
            if any(values.get(side) is None for side in ('home', 'away')):
                continue
            if market == 'spread' and abs(values['home'] + values['away']) > .001:
                continue
            month, day, hour, minute = date.groups()
            key = (home, away, month, int(day), int(hour), int(minute), market)
            quote = dict(values, updated_at=updated.isoformat())
            markets[key] = None if key in markets else quote
    result = {}
    for g in slate.to_dict('records'):
        kickoff = g.get('kickoff_ct')
        if g.get('completed') or pd.isna(kickoff) or not now < kickoff <= now + pd.Timedelta(days=14):
            continue
        eastern = kickoff.tz_convert('America/New_York')
        key = (g['home_team'], g['away_team'], eastern.strftime('%b'), eastern.day, eastern.hour, eastern.minute)
        quote = dict(source='FanDuel', feed='Covers', source_url=URL, fetched_at=fetched.isoformat(),
                     home_moneyline=None, away_moneyline=None, home_spread=None, away_spread=None)
        updates = []
        for market in ('moneyline', 'spread'):
            found = markets.get(key + (market,))
            if found:
                for side in ('home', 'away'):
                    quote[f'{side}_{market}'] = found[side]
                updates.append(found['updated_at'])
        if updates:
            quote['updated_at'] = min(updates)
            result[str(g['game_id'])] = quote
    return result
