import pandas as pd
from sunday_slate.coach_ats import coach_history, context
from sunday_slate.ui import coach_ats_panel


def row(gid, day, **kw):
    return dict(game_id=gid, gameday=day, season=2026, game_type='REG',
                home_coach='Home Coach', away_coach='Road Coach', home_team='GB', away_team='DAL',
                home_score=24, away_score=20, spread_line=3, location='Home', **kw)


def test_sign_pushes_neutral_and_pregame_cutoff():
    rows=[row('win','2026-09-01'),row('push','2026-09-08'),row('neutral','2026-09-15'),
          row('current','2026-10-18'),row('future','2026-11-01')]
    rows[1]['spread_line']=4
    rows[2]['location']='Neutral'
    game=dict(rows[3])
    hist=coach_history(pd.DataFrame(rows))
    dk=dict(source='DraftKings', home_spread=-3, away_spread=3)
    result=context(game,hist,dk,now=pd.Timestamp('2026-10-20T12:00Z'))
    away,home=result
    assert away['venue_record']==dict(wins=0,losses=1,pushes=1,games=2,pct=0)
    assert home['venue_record']==dict(wins=1,losses=0,pushes=1,games=2,pct=100)
    assert away['situations'][0]['role']=='Underdog'
    assert away['situations'][0]['role_record']['games']==3
    assert away['situations'][0]['combined_record']['games']==2
    assert '0–1–1' in coach_ats_panel(result)


def test_missing_line_no_guessing_and_book_disagreement():
    game=row('current','2026-10-18')
    hist=coach_history(pd.DataFrame([row('prior','2026-09-01')]))
    args=dict(now=pd.Timestamp('2026-10-13T12:00Z'))
    result=context(game,hist,**args)
    assert result[0]['situations']==[]
    dk=dict(source='DraftKings',home_spread=-1,away_spread=1)
    fd=dict(source='FanDuel',home_spread=1,away_spread=-1)
    result=context(game,hist,dk,fd,**args)
    assert [x['role'] for x in result[0]['situations']]==['Underdog','Favorite']


def test_only_head_coach_regular_season_since_2019_valid_results():
    rows=[row('old','2018-09-01'),row('playoff','2026-09-01'),row('missing','2026-09-01'),row('valid','2026-09-01')]
    rows[0]['season']=2018;rows[1]['game_type']='WC';rows[2]['spread_line']=None
    hist=coach_history(pd.DataFrame(rows))
    assert len(hist)==2 and set(hist.game_id)=={'valid'}
    assert coach_history(pd.DataFrame()).empty
