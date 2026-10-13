"""Research-only NFL opponent-adjusted EPA and QB usage study, no sportsbook odds.
All inputs frozen before a game-week; fit only on 2019-2022. 2023-2025
is retrospectively evaluated and 2026 preliminary. Prior passer is NOT
a verified future starter.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sunday_slate.model import predict_regular_season
from research.test_qbr_defense import load_games, load_qbr, _leading_passer_qbr, normalized

TRAIN=(2019,2020,2021,2022)
TEST=(2023,2024,2025)
YEARS=TRAIN+TEST+(2026,)
FIELDS={'season','week','game_id','team','opponent_team','season_type',
        'passing_epa','attempts','rushing_epa','carries'}
SHRINK=3
ADJUST=.5

def load_stats(path=None):
    if path:
        stats=pd.read_csv(path,low_memory=False)
    else:
        import nflreadpy
        stats=pd.DataFrame(nflreadpy.load_team_stats(
            seasons=list(YEARS), summary_level='week').to_dicts())
    if not FIELDS.issubset(stats):
        raise ValueError('Missing team EPA columns: '+str(FIELDS-set(stats)))
    x=stats[list(FIELDS)].copy()
    for c in ('season','week','passing_epa','attempts','rushing_epa','carries'):
        x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x[x.season.isin(YEARS)&x.season_type.eq('REG')].copy()
    x['team']=x.team.map(normalized)
    x['opponent_team']=x.opponent_team.map(normalized)
    x=x.dropna(subset=list(FIELDS-{'season_type'}))
    x=x[x.attempts.gt(0)&x.carries.gt(0)].copy()
    if x.duplicated(['game_id','team']).any():
        raise ValueError('Duplicate team/game EPA records')
    return x

def blank():
    d={'n':0}
    for prefix in ('p','r'):
        for suffix in ('off_sum','off_den','def_sum','def_den'):
            d[prefix+'_'+suffix]=0.
        d['a'+prefix+'_off_sum']=0.
        d['a'+prefix+'_def_sum']=0.
    return d

def rate(s,n,d):
    return s[n]/s[d] if s[d] else 0.

def make_features(schedule,stats,qbr):
    games=schedule[schedule.season.isin(YEARS)&schedule.game_type.eq('REG')].copy()
    games=games.sort_values(['season','week','game_id'],kind='stable')
    lookup={(str(r.game_id),str(r.team)):r for r in stats.itertuples(index=False)}
    output=[]
    for season,year in games.groupby('season',sort=True):
        states=defaultdict(blank)
        qbyear=qbr[qbr.season.eq(season)]
        for week,slate in year.groupby('week',sort=True):
            leaders=_leading_passer_qbr(qbyear,int(week),min_plays=30)
            changes=[]
            for g in slate.itertuples(index=False):
                h,a=normalized(g.home_team),normalized(g.away_team)
                if pd.isna(g.home_score) or pd.isna(g.away_score) or g.home_score==g.away_score:
                    continue
                H,A=states[h],states[a]
                minimum=min(H['n'],A['n'])
                shrink=minimum/(minimum+SHRINK) if minimum else 0.
                features={}
                for k in ('p','r'):
                    hoff=rate(H,k+'_off_sum',k+'_off_den')
                    aoff=rate(A,k+'_off_sum',k+'_off_den')
                    hdef=rate(H,k+'_def_sum',k+'_def_den')
                    adef=rate(A,k+'_def_sum',k+'_def_den')
                    adjhoff=rate(H,'a'+k+'_off_sum',k+'_off_den')
                    adjaoff=rate(A,'a'+k+'_off_sum',k+'_off_den')
                    adjhdef=rate(H,'a'+k+'_def_sum',k+'_def_den')
                    adjadef=rate(A,'a'+k+'_def_sum',k+'_def_den')
                    features[k+'_raw']=((hoff-adef)-(aoff-hdef))*shrink
                    features[k+'_adj']=((adjhoff-adjadef)-(adjaoff-adjhdef))*shrink
                Hq,Aq=leaders.get(h),leaders.get(a)
                qdelta=(Hq['qbr']-Aq['qbr'])/20. if Hq and Aq else 0.
                output.append({
                    'game_id':g.game_id,'season':int(season),'week':int(week),
                    'min_games':minimum,'p_raw':features['p_raw'],
                    'r_raw':features['r_raw'],'p_adj':features['p_adj'],
                    'r_adj':features['r_adj'],'qbr_delta':qdelta,
                    'qb_both_known':int(bool(Hq and Aq))
                })
            # Every team's opponent-strength reference is pre-week only.
            for g in slate.itertuples(index=False):
                h,a=normalized(g.home_team),normalized(g.away_team)
                hr=lookup.get((str(g.game_id),h))
                ar=lookup.get((str(g.game_id),a))
                if hr is None or ar is None:continue
                if str(hr.opponent_team)!=a or str(ar.opponent_team)!=h:continue
                if pd.isna(g.home_score) or pd.isna(g.away_score):continue
                for t,op,own,opp in ((h,a,hr,ar),(a,h,ar,hr)):
                    S,O=states[t],states[op]
                    change={'team':t}
                    for k,numer,den in [('p','passing_epa','attempts'),
                                        ('r','rushing_epa','carries')]:
                        off=float(getattr(own,numer))
                        offen=float(getattr(own,den))
                        deff=float(getattr(opp,numer))
                        defden=float(getattr(opp,den))
                        oppdef=(rate(O,k+'_def_sum',k+'_def_den')
                                *O['n']/(O['n']+SHRINK)) if O['n'] else 0.
                        oppoff=(rate(O,k+'_off_sum',k+'_off_den')
                                *O['n']/(O['n']+SHRINK)) if O['n'] else 0.
                        change.update({
                            k+'_off_sum':off,k+'_off_den':offen,
                            k+'_def_sum':deff,k+'_def_den':defden,
                            'a'+k+'_off_sum':off-ADJUST*oppdef*offen,
                            'a'+k+'_def_sum':deff-ADJUST*oppoff*defden
                        })
                    changes.append(change)
            # IMPORTANT: This update takes place only after all forecasts
            # for this week have been computed.
            for c in changes:
                S=states[c['team']]
                S['n']+=1
                for key,value in c.items():
                    if key!='team':S[key]+=value
    return pd.DataFrame(output)

def evaluate(sub,probs):
    if len(sub)==0:return {'n':0,'wins':0,'losses':0,'accuracy':None,'brier':None}
    y=sub.actual_home_win.astype(bool).to_numpy()
    p=np.asarray(probs,dtype=float)
    if len(p)!=len(y) or not np.isfinite(p).all():
        raise ValueError('Invalid prediction probabilities')
    w=int(((p>=.5)==y).sum());n=len(sub)
    return {'n':n,'wins':w,'losses':n-w,'accuracy':round(w/n,4),
            'brier':round(float(((p-y.astype(float))**2).mean()),5)}

def assess(games,team_stats,qbr):
    baseline=predict_regular_season(games)
    features=make_features(games,team_stats,qbr)
    data=baseline.merge(features,on='game_id',validate='one_to_one')
    data=data[data.pick_result.isin(['Correct','Incorrect'])].copy()
    data['actual_home_win']=(data.pick_result.eq('Correct')
                             ==data.predicted_winner.eq(data.home_team))
    data['eloDiff']=(data.home_elo-data.away_elo
                     +data.home_field_elo+data.rest_elo)/100.
    # A small predeclared suite. Models are never refit on 2023+.
    choices={
        'elo_recalibrated':['eloDiff'],
        'elo_raw_epa':['eloDiff','p_raw','r_raw'],
        'elo_opponent_adjusted_epa':['eloDiff','p_adj','r_adj'],
        'elo_qbr_proxy':['eloDiff','qbr_delta','qb_both_known'],
        'elo_adj_epa_qbr':['eloDiff','p_adj','r_adj','qbr_delta','qb_both_known'],
        'elo_raw_epa_qbr':['eloDiff','p_raw','r_raw','qbr_delta','qb_both_known'],
    }
    fit=data[data.season.isin(TRAIN)]
    if len(fit)<900:raise ValueError('Incomplete training data: '+str(len(fit)))
    for name,cols in choices.items():
        clf=make_pipeline(StandardScaler(),LogisticRegression(
            C=1.0,max_iter=1500,solver='lbfgs'))
        clf.fit(fit[cols].fillna(0),fit.actual_home_win.astype(int))
        data[name]=clf.predict_proba(data[cols].fillna(0))[:,1]
    periods={'2019-2022_fit':list(TRAIN),'2023-2025_evaluation':list(TEST),
             '2026_preliminary':[2026]}
    periods.update({str(y):[y] for y in range(2019,2027)})
    results={}
    for key,years in periods.items():
        sub=data[data.season.isin(years)]
        report={'baseline':evaluate(sub,sub.home_probability),
                'qb_coverage':{'both_qbs':int(sub.qb_both_known.sum()),
                               'total':len(sub)}}
        for name in choices:report[name]=evaluate(sub,sub[name])
        results[key]=report
    return {'method':{'fit_years':list(TRAIN),
                      'prior_only_weekly_freeze':True,
                      'epa_opponent_adjustment':
                          'Pre-week opponent efficiency residual; beta=.5, sample shrink n/(n+3)',
                      'qbr':'Previous 4-week highest-usage QB ESPN Total QBR, not confirmed next starter',
                      'draftkings_lines_used':False},
            'counts':{'team_rows':len(team_stats),'qbr_rows':len(qbr),
                      'feature_rows':len(features),'graded_games':len(data)},
            'results':results,
            'disclaimer':'Historical retrospective comparison, no live model changes; 2026 incomplete'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--games')
    parser.add_argument('--team')
    parser.add_argument('--qbr')
    parser.add_argument('--output',default='epa_qbr_model_results.json')
    args=parser.parse_args()
    games=load_games(args.games)
    print('Schedule games loaded:',len(games),flush=True)
    team=load_stats(args.team)
    print('Weekly EPA team lines:',len(team),flush=True)
    qbr=load_qbr(args.qbr)
    print('ESPN QBR lines:',len(qbr),flush=True)
    report=assess(games,team,qbr)
    data=json.dumps(report,indent=2,allow_nan=False)
    print('EPA_QBR_RESULT_BEGIN')
    print(data)
    print('EPA_QBR_RESULT_END',flush=True)
    Path(args.output).write_text(data+'\n')

if __name__=='__main__':main()
