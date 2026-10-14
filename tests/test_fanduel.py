"""FanDuel display must never borrow DraftKings or reference prices."""
import pandas as pd
from test_draftkings_coaching import event, game
from sunday_slate.draftkings import parse_event, match_games
from sunday_slate.metrics import with_kickoffs
from sunday_slate.ui import game_card
from sunday_slate.coach_flags import coaching_flags


def test_book_isolation():
    payload = event()
    for market in payload['markets']:
        for participant in market['participants']:
            price = participant['lines'][0]['prices']
            price['23'] = dict(price['19'], price=150 if market['market_id'] == 1 else -110)
    assert parse_event(payload, 'FanDuel')['home_moneyline'] == 150
    assert parse_event(payload)['home_moneyline'] == -140
    assert parse_event(event(), 'FanDuel')['home_moneyline'] is None
    assert parse_event(event(book='23'))['home_moneyline'] is None


def test_card_and_flags():
    row = game()
    df = with_kickoffs(pd.DataFrame([row]))
    quotes = match_games(df, {'2026-10-18': {'events': [event(book='23')]}}, 'FanDuel')
    quote = quotes[row['game_id']]
    assert quote['source'] == 'FanDuel'
    assert coaching_flags(df, 2026, 6, quotes) == {}
    # Fixed far-future kickoff keeps rendering test independent of today's date.
    rendered_row = df.iloc[0].copy()
    rendered_row['kickoff_ct'] = pd.Timestamp('2099-10-18', tz='America/Chicago')
    html = game_card(rendered_row, {}, {}, fd_quote=quote)
    assert 'FanDuel' not in html
    assert 'Odds unavailable' in html
    rendered_row['completed'] = True
    rendered_row['home_score'], rendered_row['away_score'] = 24, 17
    assert '<td>FanDuel</td>' not in game_card(rendered_row, {}, {}, fd_quote=quote)


def test_missing_and_wrong_date():
    row = game()
    df = with_kickoffs(pd.DataFrame([row]))
    payload = event(book='23')
    payload['event_date'] = '2026-10-19T17:00:00Z'
    assert match_games(df, {'2026-10-19': {'events': [payload]}}, 'FanDuel') == {}
