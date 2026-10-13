"""No-key ESPN published pregame quotes, retaining sportsbook identity."""
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import pandas as pd
from sunday_slate.draftkings import _team, _number
from sunday_slate.market import valid_american


class ESPNFeedError(RuntimeError):
    pass


def fetch_week(season, week, season_type=2):
    url = ('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
           f'?dates={int(season)}&seasontype={int(season_type)}&week={int(week)}&limit=100')
    try:
        with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=12) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
            raise ValueError('Invalid scoreboard')
        payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
        return payload
    except Exception as exc:
        raise ESPNFeedError('ESPN odds unavailable') from exc


def match_quotes(slate, payload, now=None):
    """Match exact teams and UTC kickoff; never relabel or use opening prices."""
    result = {'DraftKings': {}, 'FanDuel': {}}
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    keyed = {}
    for event in payload.get('events', []):
        for comp in event.get('competitions', []):
            status = comp.get('status', {}).get('type', {})
            if status.get('state') != 'pre' or status.get('completed'):
                continue
            kickoff = pd.to_datetime(comp.get('date'), utc=True, errors='coerce')
            if pd.isna(kickoff) or kickoff <= now:
                continue
            sides = {}
            for side in comp.get('competitors', []):
                team = side.get('team', {})
                sides[side.get('homeAway')] = _team(team.get('displayName')) or _team(team.get('abbreviation'))
            if not sides.get('home') or not sides.get('away') or sides['home'] == sides['away']:
                continue
            for odds in comp.get('odds', []):
                name = str(odds.get('provider', {}).get('name', '')).lower().replace(' ', '')
                book = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}.get(name)
                if not book:
                    continue
                quote = dict(source=book, feed='ESPN', fetched_at=payload.get('fetched_at'), updated_at=None)
                for side in ('home', 'away'):
                    ml = odds.get('moneyline', {}).get(side, {}).get('close', {}).get('odds')
                    if ml is None:
                        ml = odds.get(side + 'TeamOdds', {}).get('moneyLine')
                    quote[side + '_moneyline'] = valid_american(ml)
                    spread = odds.get('pointSpread', {}).get(side, {}).get('close', {}).get('line')
                    if spread is None:
                        spread = _number(odds.get('spread'))
                        if spread is not None and side == 'away':
                            spread = -spread
                    spread = _number(spread)
                    quote[side + '_spread'] = spread if spread is not None and abs(spread) <= 30 else None
                hs, aws = quote['home_spread'], quote['away_spread']
                if hs is None or aws is None or abs(hs + aws) > .001:
                    quote['home_spread'] = quote['away_spread'] = None
                if all(quote[k] is None for k in ('home_spread', 'away_spread', 'home_moneyline', 'away_moneyline')):
                    continue
                key = (book, sides['home'], sides['away'], kickoff)
                keyed[key] = None if key in keyed else quote
    for g in slate.to_dict('records'):
        kickoff = g.get('kickoff_ct')
        if g.get('completed') or pd.isna(kickoff) or kickoff <= now:
            continue
        for book in result:
            quote = keyed.get((book, g['home_team'], g['away_team'], kickoff))
            if quote:
                result[book][str(g['game_id'])] = quote
    return result
