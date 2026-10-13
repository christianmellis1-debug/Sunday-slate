import pandas as pd
from sunday_slate.espn_odds import match_quotes


def fixture():
    odds = {'provider': {'name': 'DraftKings'}, 'spread': 2.5,
            'moneyline': {'home': {'close': {'odds': '+124'}}, 'away': {'close': {'odds': '-148'}}}}
    comp = {'date': '2099-10-16T00:15Z', 'status': {'type': {'state': 'pre'}},
            'competitors': [{'homeAway': 'home', 'team': {'displayName': 'Denver Broncos'}},
                            {'homeAway': 'away', 'team': {'displayName': 'Seattle Seahawks'}}], 'odds': [odds]}
    slate = pd.DataFrame([dict(game_id='g', home_team='DEN', away_team='SEA', completed=False,
                              kickoff_ct=pd.Timestamp(comp['date']))])
    return slate, {'events': [{'competitions': [comp]}]}, comp, odds


def test_book_and_sign():
    slate, payload, comp, odds = fixture()
    quotes = match_quotes(slate, payload)
    assert quotes['FanDuel'] == {}
    q = quotes['DraftKings']['g']
    assert q['home_moneyline'] == 124 and q['away_moneyline'] == -148
    assert q['home_spread'] == 2.5 and q['away_spread'] == -2.5
    odds['provider']['name'] = 'FanDuel'
    quotes = match_quotes(slate, payload)
    assert quotes['DraftKings'] == {} and quotes['FanDuel']['g']['source'] == 'FanDuel'


def test_no_opening_live_wrong_game_or_duplicate_quotes():
    slate, payload, comp, odds = fixture()
    odds['moneyline'] = {'home': {'open': {'odds': '-150'}}}
    assert match_quotes(slate, payload)['DraftKings']['g']['home_moneyline'] is None
    comp['status']['type']['state'] = 'in'
    assert not match_quotes(slate, payload)['DraftKings']
    comp['status']['type']['state'] = 'pre'
    slate.loc[0, 'home_team'] = 'DAL'
    assert not match_quotes(slate, payload)['DraftKings']
    slate.loc[0, 'home_team'] = 'DEN'
    comp['odds'].append(odds)
    assert not match_quotes(slate, payload)['DraftKings']
