"""Situational head-coach ATS history, using pre-match nflverse reference spreads."""
import math
import pandas as pd

START_SEASON = 2019


def coach_history(schedule):
    cols = ['coach', 'venue', 'role', 'result', 'season', 'game_id', 'day']
    needed = {'game_id', 'season', 'game_type', 'gameday', 'home_coach', 'away_coach',
              'home_score', 'away_score', 'spread_line', 'location'}
    if not needed.issubset(schedule.columns):
        return pd.DataFrame(columns=cols)
    rows = []
    for g in schedule.drop_duplicates('game_id', keep=False).to_dict('records'):
        try:
            season = int(g['season'])
            hs, aws, line = float(g['home_score']), float(g['away_score']), float(g['spread_line'])
        except (ValueError, TypeError, OverflowError):
            continue
        if g['game_type'] != 'REG' or season < START_SEASON or not all(map(math.isfinite, (hs, aws, line))):
            continue
        day = pd.to_datetime(g['gameday'], errors='coerce', utc=True)
        if pd.isna(day):
            continue
        # nflverse positive spread_line means HOME favored (opposite a team handicap).
        home_margin = hs - aws - line
        for side, margin, handicap in [('home', home_margin, -line), ('away', -home_margin, line)]:
            coach = g.get(side + '_coach')
            if not isinstance(coach, str) or not coach.strip():
                continue
            venue = 'Neutral' if str(g['location']).lower() == 'neutral' else (
                ('Home' if side == 'home' else 'Road') if str(g['location']).lower() == 'home' else 'Unknown')
            rows.append(dict(coach=coach.strip().casefold(), venue=venue,
                             role='Favorite' if handicap < 0 else 'Underdog' if handicap > 0 else "Pick’em",
                             result='W' if margin > .001 else 'L' if margin < -.001 else 'P',
                             season=season, game_id=str(g['game_id']), day=day))
    return pd.DataFrame(rows, columns=cols)


def record(rows):
    wins = int(rows.result.eq('W').sum())
    losses = int(rows.result.eq('L').sum())
    pushes = int(rows.result.eq('P').sum())
    return dict(wins=wins, losses=losses, pushes=pushes, games=len(rows),
                pct=100*wins/(wins+losses) if wins+losses else None)


def context(game, history, dk_quote=None, fd_quote=None, now=None):
    now = pd.Timestamp(now or pd.Timestamp.now(tz='UTC'))
    day = pd.to_datetime(game.get('gameday'), utc=True, errors='coerce')
    if pd.isna(day):
        return []
    # Exclude the entire matchup date, the current game, and future outcomes.
    cutoff = min(day, now.normalize())
    past = history[(history.day < cutoff) & (history.game_id != str(game.get('game_id')))]
    output = []
    for side in ('away', 'home'):
        name = game.get(side + '_coach')
        name = name.strip() if isinstance(name, str) and name.strip() else None
        venue = 'Neutral' if str(game.get('location')).lower() == 'neutral' else (
            ('Home' if side == 'home' else 'Road') if str(game.get('location')).lower() == 'home' else 'Unknown')
        eligible = past[past.coach == name.casefold()] if name else past.iloc[:0]
        item = dict(team=str(game.get(side+'_team')), coach=name, venue=venue,
                    venue_record=record(eligible[eligible.venue == venue]), situations=[],
                    seasons=f'{START_SEASON}–{int(game.get("season", START_SEASON))}')
        for book, quote in [('DraftKings', dk_quote), ('FanDuel', fd_quote)]:
            if not isinstance(quote, dict) or quote.get('source') != book:
                continue
            try:
                home, away = float(quote['home_spread']), float(quote['away_spread'])
            except (KeyError, TypeError, ValueError):
                continue
            if not all(map(math.isfinite, (home, away))) or abs(home+away) > .001:
                continue
            handicap = home if side == 'home' else away
            role = 'Favorite' if handicap < 0 else 'Underdog' if handicap > 0 else 'Pick’em'
            # Same situation at both books only needs one set of records.
            if any(x['role'] == role for x in item['situations']):
                continue
            relevant = eligible[eligible.role == role]
            item['situations'].append(dict(book=book, role=role, spread=handicap,
                role_record=record(relevant), combined_record=record(relevant[relevant.venue == venue])))
        output.append(item)
    return output
