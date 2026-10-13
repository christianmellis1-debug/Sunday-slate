import pandas as pd
from sunday_slate.fanduel_covers import match_quotes

NOW = pd.Timestamp('2026-10-13T21:00:00Z')

def fixture(book='FanDuel', stamp=None, home='LA'):
    stamp = int((NOW - pd.Timedelta(minutes=15)).timestamp()) if stamp is None else stamp
    def row(market, away, home_value):
        return f'''<table id="{market}-table"><tr class="oddsGameRow">
        <div class="game-time">Oct 18, 16:05</div><div class="teams-div">
        <div class="away-cell"><strong>ARI</strong></div><div class="home-cell"><strong>{home}</strong></div></div>
        <td data-book="{book}" data-date="{stamp}">
        <div class="away-cell"><a class="odds-cta" data-linkcont="odds_click-{market}-fanduel">{away}</a></div>
        <div class="home-cell"><a class="odds-cta" data-linkcont="odds_click-{market}-fanduel">{home_value}</a></div>
        </td></tr></table>'''
    html = row('moneyline','<span class="__american">+640</span>','<span class="__american">-950</span>')
    html += row('spread','+13.5 <span class="__american">-115</span>','-13.5 <span class="__american">-111</span>')
    slate = pd.DataFrame([dict(game_id='g',home_team='LAR',away_team='ARI',completed=False,kickoff_ct=pd.Timestamp('2026-10-18T20:05:00Z'))])
    return slate, {'html':html,'fetched_at':NOW.isoformat()}


def test_prices_and_alias():
    slate, snap = fixture()
    q = match_quotes(slate,snap,now=NOW)['g']
    assert q['source'] == 'FanDuel' and q['feed'] == 'Covers'
    assert q['home_moneyline'] == -950 and q['away_moneyline'] == 640
    assert q['home_spread'] == -13.5 and q['away_spread'] == 13.5


def test_missing_stale_wrong_book_and_wrong_game_fail_closed():
    for args in [dict(book='DraftKings'), dict(stamp=0), dict(home='DEN')]:
        slate,snap = fixture(**args)
        assert match_quotes(slate,snap,now=NOW) == {}
    slate,snap = fixture()
    snap['fetched_at'] = (NOW-pd.Timedelta(hours=1)).isoformat()
    assert match_quotes(slate,snap,now=NOW) == {}
    slate,snap = fixture()
    slate.loc[0,'kickoff_ct'] += pd.Timedelta(days=1)
    assert match_quotes(slate,snap,now=NOW) == {}
    slate,snap = fixture()
    slate.loc[0,'completed'] = True
    assert match_quotes(slate,snap,now=NOW) == {}


def test_opening_lines_are_not_used():
    slate,snap = fixture()
    snap['html'] = snap['html'].replace('data-book="FanDuel"','data-book="Opening"')
    assert match_quotes(slate,snap,now=NOW) == {}
