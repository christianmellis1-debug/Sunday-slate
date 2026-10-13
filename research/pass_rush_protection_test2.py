"""Sunday Slate Test 2: Pass Rush vs Offensive Line Protection.

Research-only. Official NFL-ELO-1.0 is unchanged.

Design locked before viewing holdout:
- Pressure proxy = QB hit OR sack on a recorded dropback (NOT proprietary true pressure)
- Sack-only independent sensitivity
- All input rates pre-WEEK, never game-week statistics
- Minimum 3 previous team games for qualification; defense top quartile
  vs opponent offensive allowed-pressure top quartile, one side only
- Development 2019-22; holdout 2023-25; provisional 2026
- nflverse spread_line is home-favored closing/reference spread (NOT FanDuel)
- Train full-slate logistic once on development, never on holdout
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sunday_slate.data import load_schedules
from sunday_slate.model import predict_regular_season

TRAIN=(2019,2020,2021,2022)
TEST=(2023,2024,2025)
CURRENT=(2026,)
YEARS=TRAIN+TEST+CURRENT
MIN_GAMES=3
PRIOR_DROPS=150.
PBP_COLS={"game_id","season","week","season_type","posteam","defteam",
          "qb_dropback","sack","qb_hit"}
ALIASES={"LAR":"LA","JAC":"JAX","WSH":"WAS","SD":"LAC","OAK":"LV"}

def normal(team):
    v=str(team).upper()
    return ALIASES.get(v,v)

def load_pbp_aggregates(path=None):
    if path:
        return validate_agg(pd.read_csv(path,low_memory=False))
    import nflreadpy
    import polars as pl
    parts=[]
    for year in YEARS:
        raw=nflreadpy.load_pbp(seasons=[int(year)])
        missing=PBP_COLS-set(raw.columns)
        if missing:
            raise ValueError(f"{year} PBP lacks {sorted(missing)}")
        x=raw.select(sorted(PBP_COLS))
        x=x.filter((pl.col("season_type")=="REG")&
                   (pl.col("qb_dropback")==1)&
                   pl.col("posteam").is_not_null()&
                   pl.col("defteam").is_not_null()&
                   pl.col("sack").is_not_null())
        x=x.with_columns([
           ((pl.col("sack")==1)|(pl.col("qb_hit")==1)).cast(pl.Int64).alias("pressure"),
           pl.col("qb_hit").is_not_null().cast(pl.Int64).alias("has_hit"),
           pl.col("sack").cast(pl.Int64).alias("sacked"),
        ])
        agg=x.group_by(["season","week","game_id","posteam","defteam"]).agg(
            pl.len().alias("dropbacks"),
            pl.col("has_hit").sum().alias("hit_observed"),
            pl.col("pressure").sum().alias("pressures"),
            pl.col("sacked").sum().alias("sacks"),
        )
        df=agg.to_pandas()
        print(f"PBP_YEAR {year} source plays={x.height} team-game rows={len(df)} "
              f"QB-hit known={df.hit_observed.sum()/max(1,df.dropbacks.sum()):.3f}",flush=True)
        parts.append(df)
    return validate_agg(pd.concat(parts,ignore_index=True))

def validate_agg(raw):
    fields={"season","week","game_id","posteam","defteam","dropbacks",
            "hit_observed","pressures","sacks"}
    if not fields.issubset(raw):
        raise ValueError("Aggregate missing "+str(fields-set(raw)))
    frame=raw.copy()
    for col in ("season","week","dropbacks","hit_observed","pressures","sacks"):
        frame[col]=pd.to_numeric(frame[col],errors="coerce")
    frame=frame[frame.season.isin(YEARS)].dropna(
        subset=["season","week","game_id","posteam","defteam","dropbacks",
                "hit_observed","pressures","sacks"]).copy()
    for col in ("posteam","defteam"):
        frame[col]=frame[col].map(normal)
    frame=frame[frame.dropbacks.gt(0)]
    if frame.duplicated(["game_id","posteam"]).any():
        raise ValueError("Ambiguous game/team dropback lines")
    if (frame.pressures>frame.dropbacks).any() or (frame.sacks>frame.dropbacks).any():
        raise ValueError("Invalid impossible pressures/sacks")
    return frame

def blank():
    return {"n":0,"off_drop":0.,"off_press":0.,"off_sack":0.,
            "def_drop":0.,"def_press":0.,"def_sack":0.,
            "off_resid":0.,"def_resid":0.,
            "history":[]}

def rate(part,kind,typ="press",pseudo=PRIOR_DROPS):
    den=part[f"{kind}_drop"]
    if not den:return 0.1 if typ=="press" else .07
    base=.1 if typ=="press" else .07
    return (part[f"{kind}_{typ}"]+base*pseudo)/(den+pseudo)

def features_schedule(schedule, aggregates):
    season_games=schedule.loc[schedule.game_type.eq("REG")
                              & schedule.season.isin(YEARS)].copy().sort_values(
                                  ["season","week","game_id"],kind="stable")
    look={(str(r.game_id),str(r.posteam)):r for r in aggregates.itertuples(index=False)}
    features=[]
    coverage={"graded_games":0,"observed_preweek_eligible":0,
              "eligible_pbp_updates":0,"missing_pbp_updates":0}
    for year, games in season_games.groupby("season",sort=True):
        states=defaultdict(blank)
        for week, slate in games.groupby("week",sort=True):
            qualified={team:s for team,s in states.items()
                       if s["n"]>=MIN_GAMES and s["off_drop"]>=100 and s["def_drop"]>=100}
            def_vals=[rate(s,"def") for s in qualified.values()]
            off_vals=[rate(s,"off") for s in qualified.values()]
            cuts=(float(np.quantile(def_vals,.75)),
                  float(np.quantile(off_vals,.75))) if len(qualified)>=20 else None
            for g in slate.to_dict("records"):
                h,a=normal(g["home_team"]),normal(g["away_team"])
                H,A=states[h],states[a]
                # Margin of pressure on visiting QB minus home QB.
                raw=.5*(rate(H,"def")+rate(A,"off")-
                        rate(A,"def")-rate(H,"off"))
                # Prior-only opponent quality subtraction (centered on 0).
                defH=H["def_resid"]/(H["def_drop"]+PRIOR_DROPS)
                defA=A["def_resid"]/(A["def_drop"]+PRIOR_DROPS)
                offH=H["off_resid"]/(H["off_drop"]+PRIOR_DROPS)
                offA=A["off_resid"]/(A["off_drop"]+PRIOR_DROPS)
                adjusted=.5*(defH+offA-defA-offH)
                sacks=.5*(rate(H,"def","sack")+rate(A,"off","sack")-
                          rate(A,"def","sack")-rate(H,"off","sack"))
                def recent(part,side):
                    xs=part["history"][-4:]
                    total=sum(x[side+"_drop"] for x in xs)
                    events=sum(x[side+"_press"] for x in xs)
                    return (events+.1*PRIOR_DROPS)/(total+PRIOR_DROPS)
                recent=.5*(recent(H,"def")+recent(A,"off")
                           -recent(A,"def")-recent(H,"off"))
                qualifying=h in qualified and a in qualified
                sel=None
                if qualifying and cuts is not None:
                    def_cut,off_cut=cuts
                    h_yes=(rate(H,"def")>=def_cut and rate(A,"off")>=off_cut)
                    a_yes=(rate(A,"def")>=def_cut and rate(H,"off")>=off_cut)
                    if h_yes!=a_yes:
                        sel=h if h_yes else a
                hs,aw=g["home_score"],g["away_score"]
                if pd.notna(hs) and pd.notna(aw) and hs!=aw:
                    coverage["graded_games"]+=1
                    if qualifying:coverage["observed_preweek_eligible"]+=1
                features.append({
                    "game_id":str(g["game_id"]),"season":int(year),"week":int(week),
                    "raw_edge":raw*10.,
                    "adjusted_edge":adjusted*10.,
                    "recent_edge":recent*10.,
                    "sack_edge":sacks*10.,
                    "has_min_games":int(qualifying),
                    "min_games":min(H["n"],A["n"]),
                    "dom_team":sel or "",
                    "dom_home":int(sel==h) if sel else 0,
                    "dom_away":int(sel==a) if sel else 0,
                    "home_def_press":rate(H,"def") if H["n"] else None,
                    "away_def_press":rate(A,"def") if A["n"] else None,
                    "home_off_press_allowed":rate(H,"off") if H["n"] else None,
                    "away_off_press_allowed":rate(A,"off") if A["n"] else None,
                })
            # Process completed prior games AFTER all week's features fixed.
            updates=[]
            for g in slate.to_dict("records"):
                if pd.isna(g["home_score"]) or pd.isna(g["away_score"]):
                    continue
                H,A=normal(g["home_team"]),normal(g["away_team"])
                hr=look.get((str(g["game_id"]),H))
                ar=look.get((str(g["game_id"]),A))
                if hr is None or ar is None:
                    coverage["missing_pbp_updates"]+=1
                    continue
                if (normal(hr.defteam)!=A or normal(ar.defteam)!=H
                    or int(hr.week)!=int(week) or int(ar.week)!=int(week)
                    or int(hr.season)!=int(year) or int(ar.season)!=int(year)):
                    raise ValueError(f"Game/PBP team disagreement {g['game_id']}")
                updates.append((H,A,hr,ar))
            # All residual expectations use prior-week opponent rates.
            changes=[]
            for H,A,hr,ar in updates:
                oh=states[H];oa=states[A]
                for team,opp,own,allowed in [
                    (H,A,hr,ar),(A,H,ar,hr)]:
                    S,O=states[team],states[opp]
                    offensive=float(own.pressures)/float(own.dropbacks)
                    defensive=float(allowed.pressures)/float(allowed.dropbacks)
                    changes.append((team,{
                        "off_drop":float(own.dropbacks),
                        "off_press":float(own.pressures),
                        "off_sack":float(own.sacks),
                        "def_drop":float(allowed.dropbacks),
                        "def_press":float(allowed.pressures),
                        "def_sack":float(allowed.sacks),
                        "off_resid":(offensive-rate(O,"def"))*float(own.dropbacks),
                        "def_resid":(defensive-rate(O,"off"))*float(allowed.dropbacks),
                    }))
                coverage["eligible_pbp_updates"]+=1
            for team,c in changes:
                S=states[team]
                S["n"]+=1
                for key in ("off_drop","off_press","off_sack","def_drop",
                            "def_press","def_sack","off_resid","def_resid"):
                    S[key]+=c[key]
                S["history"].append(c)
    return pd.DataFrame(features),coverage

def evaluate_predictions(sub, probabilities):
    if len(sub)==0:return {"games":0}
    pred=np.asarray(probabilities,dtype=float)
    y=sub.actual_home_win.to_numpy(dtype=float)
    won=((pred>=.5)==(y>=.5))
    wins=int(won.sum())
    valid=sub["spread_line"].notna()
    # nflverse spread_line represents home favored points, NOT home ATS +points.
    spread=(sub.loc[valid,"home_score"]-sub.loc[valid,"away_score"]
            -sub.loc[valid,"spread_line"])
    ats_pred=pd.Series((pred>=.5),index=sub.index)
    ats_val=ats_pred.loc[valid].eq(spread>0)
    ats_not_push=spread.abs()>1e-8
    ats_games=int(ats_not_push.sum())
    ats_win=int(ats_val.loc[ats_not_push.index][ats_not_push].sum())
    return {
        "games":len(sub),"wins":wins,"losses":len(sub)-wins,
        "accuracy_pct":round(100*wins/len(sub),2),
        "brier":round(float(np.mean((pred-y)**2)),5),
        "logloss":round(float(np.mean(
            -y*np.log(np.clip(pred,1e-8,1))-
            (1-y)*np.log(np.clip(1-pred,1e-8,1)))),5),
        "ats_with_reference_line":{"wins":ats_win,"losses":ats_games-ats_win,
                                   "push":int((~ats_not_push).sum()),
                                   "cover_pct":round(100*ats_win/ats_games,2) if ats_games else None}
    }

def assess(schedule,stats):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    base=predict_regular_season(schedule)
    features,coverage=features_schedule(schedule,stats)
    data=base.merge(features.drop(columns=["season","week"]),on="game_id",
                    validate="one_to_one")
    schedule_cols=schedule[["game_id","home_score","away_score","spread_line"]]
    data=data.merge(schedule_cols,on="game_id",validate="one_to_one")
    data=data[data.season.isin(YEARS)&data.pick_result.isin(["Correct","Incorrect"])].copy()
    data["actual_home_win"]=(data.pick_result.eq("Correct")==
                             data.predicted_winner.eq(data.home_team)).astype(int)
    data["spread_line"]=pd.to_numeric(data.spread_line,errors="coerce")
    raw_p=data.home_probability.clip(1e-8,1-1e-8)
    data["elo_logit"]=np.log(raw_p/(1-raw_p))
    models={
        "elo_recalibrated":["elo_logit"],
        "elo_raw_pressure":["elo_logit","raw_edge","has_min_games"],
        "elo_opponent_adjusted_pressure":["elo_logit","adjusted_edge","has_min_games"],
        "elo_sack_only":["elo_logit","sack_edge","has_min_games"],
        "elo_recent_pressure":["elo_logit","recent_edge","has_min_games"],
        "elo_raw_plus_adjusted":["elo_logit","raw_edge","adjusted_edge","has_min_games"],
    }
    train=data[data.season.isin(TRAIN)]
    if len(train)<1000:
        raise ValueError(f"Insufficient 2019–22 fitting games: {len(train)}")
    fitted={}
    for name,cols in models.items():
        pipeline=make_pipeline(StandardScaler(),LogisticRegression(
            C=1.0,solver="lbfgs",max_iter=2000))
        pipeline.fit(train[cols].fillna(0),train.actual_home_win)
        data[name]=pipeline.predict_proba(data[cols].fillna(0))[:,1]
        coef=pipeline.named_steps["logisticregression"]
        fitted[name]={"cols":cols,"coef":coef.coef_[0].tolist(),
                      "intercept":float(coef.intercept_[0])}
    groups={"2019-2022_fit":TRAIN,"2023-2025_holdout":TEST,
            "2026_preliminary":CURRENT}
    groups.update({str(y):(y,) for y in YEARS})
    reports={}
    for period,years in groups.items():
        part=data[data.season.isin(years)].copy()
        period_result={"games":len(part),
                       "qualified_with_3_prior_games":int(part.has_min_games.sum()),
                       "dominant_matchups":int(part.dom_team.ne("").sum()),
                       "model_results":{"original_elo":evaluate_predictions(part,part.home_probability)}}
        for name in models:
            period_result["model_results"][name]=evaluate_predictions(part,part[name])
        dom=part[part.dom_team.ne("")].copy()
        def signal_report(sel):
            if not len(sel):return {"games":0}
            correct=(sel.dom_team.eq(sel.home_team)==sel.actual_home_win.astype(bool))
            wins=int(correct.sum())
            signal_home=sel.dom_team.eq(sel.home_team)
            spreads=sel.home_score-sel.away_score-sel.spread_line
            valid=spreads.notna()
            push=valid&spreads.abs().le(1e-8)
            covered=(signal_home.eq(spreads>0))&valid&~push
            atsn=int((valid&~push).sum())
            elo_same=sel.predicted_winner.eq(sel.dom_team)
            games_vs_elo=sel[~elo_same]
            return {"games":len(sel),"wins":wins,"losses":len(sel)-wins,
                    "su_pct":round(100*wins/len(sel),2),
                    "ats_reference":{"wins":int(covered.sum()),
                       "losses":atsn-int(covered.sum()),"push":int(push.sum()),
                       "cover_pct":round(100*covered.sum()/atsn,2) if atsn else None},
                    "elo_agreed_n":int(elo_same.sum()),
                    "elo_conflicted_n":int((~elo_same).sum()),
                    "signal_wins_when_elo_conflicted":int(
                        (games_vs_elo.dom_team.eq(games_vs_elo.home_team)==
                         games_vs_elo.actual_home_win.astype(bool)).sum()),
                    "signal_home_n":int(signal_home.sum())}
        period_result["dominant_signal"]={
            "all":signal_report(dom),
            "selected_underdogs":signal_report(dom.loc[
                ((dom.dom_team.eq(dom.home_team)&dom.spread_line.lt(0))|
                 (dom.dom_team.eq(dom.away_team)&dom.spread_line.gt(0)))]),
            "selected_favorites":signal_report(dom.loc[
                ((dom.dom_team.eq(dom.home_team)&dom.spread_line.gt(0))|
                 (dom.dom_team.eq(dom.away_team)&dom.spread_line.lt(0)))]),
        }
        reports[period]=period_result
    return {"method":{"train":list(TRAIN),"holdout":list(TEST),
                      "stat":"qb_hit OR sack per pass dropback (not all true pressures)",
                      "source":"nflverse play-by-play source, week-frozen raw/adjusted pressure",
                      "signal":"top-quartile defense pressure versus top-quartile opponent pressure allowed, minimum 3 prior games; exclusive pick",
                      "ats":"nflverse reference closing spread; not verified FanDuel/DraftKings",
                      "production_model_unchanged":True},
            "coverage":coverage,
            "aggregates":len(stats),"fitted":fitted,"results":reports}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stats")
    ap.add_argument("--schedule")
    ap.add_argument("--output",default="pass_rush_protection_test2_results.json")
    opts=ap.parse_args()
    schedule=(pd.read_csv(opts.schedule,low_memory=False)
              if opts.schedule else load_schedules())
    for c in ("season","week","home_score","away_score","spread_line"):
        schedule[c]=pd.to_numeric(schedule[c],errors="coerce")
    print("Loading historical QB dropbacks 2019–2026...",flush=True)
    stats=load_pbp_aggregates(opts.stats)
    print("Aggregate games:",len(stats),flush=True)
    answer=assess(schedule,stats)
    text=json.dumps(answer,indent=2,allow_nan=False)
    print("PRESSURE_TEST2_BEGIN")
    print(text)
    print("PRESSURE_TEST2_END",flush=True)
    Path(opts.output).write_text(text+"\n")
if __name__=="__main__":main()
