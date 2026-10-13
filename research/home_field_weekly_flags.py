"""Research only: pregame NFL home-field flag audit, no application modifications.

Current week candidates are model-qualified separately from market-qualified.
Historical schedule prices are snapshots, not a timestamped DraftKings feed.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from research.home_field_nfl_proposed import read_inputs,features

def scan(games,stats,years=(2026,),through_week=6):
    keyed={(r.game_id,r.team):r._asdict() for r in stats.itertuples(index=False)}
    games=games[games.season.isin(years) & games.week.le(through_week)].copy()
    rows=[]
    counts=[]
    for (season,week),slate in games.groupby(["season","week"],sort=True):
        pre=features(games,keyed,int(season),int(week))
        counts.append({"season":int(season),"week":int(week),
                       "schedule_games":len(slate),
                       "completed_games":int((slate.home_score.notna() & slate.away_score.notna()).sum()),
                       "eligible_profile_teams":len(pre)})
        for g in slate.itertuples():
            neutral="neutral" in str(g.location).lower()
            complete=pd.notna(g.home_score) and pd.notna(g.away_score)
            if neutral or g.home_team not in pre or g.away_team not in pre:
                continue
            ho,hd=pre[g.home_team];ao,ad=pre[g.away_team]
            oe=float(ho-ao);de=float(hd-ad)
            mag=min(oe,de)
            edge=oe>1e-10 and de>1e-10
            in_band=edge and .25<=mag<.5
            hml=g.home_moneyline;aml=g.away_moneyline
            price_available=pd.notna(hml) and pd.notna(aml)
            price_ok=bool(price_available and -500<float(hml)<=-100 and float(aml)>0)
            if not edge and week!=through_week:
                continue
            rows.append({
              "season":int(season),"week":int(week),"game_id":str(g.game_id),
              "date":str(g.gameday),"kickoff_et":str(g.gametime),
              "matchup":str(g.away_team)+" @ "+str(g.home_team),
              "home":str(g.home_team),"away":str(g.away_team),
              "home_off_edge":round(oe,4),"home_def_edge":round(de,4),
              "magnitude":round(mag,4),
              "both_edges_positive":bool(edge),"magnitude_025_049":bool(in_band),
              "home_moneyline":int(hml) if pd.notna(hml) else None,
              "away_moneyline":int(aml) if pd.notna(aml) else None,
              "price_known":bool(price_available),
              "home_favorite_price_ok":bool(price_ok),
              "qualifies_full_flag":bool(in_band and price_ok),
              "completed":bool(complete),
              "home_score":int(g.home_score) if pd.notna(g.home_score) else None,
              "away_score":int(g.away_score) if pd.notna(g.away_score) else None,
              "closing_spread_reference":float(g.spread_line) if pd.notna(g.spread_line) else None
            })
    return {"description":"Research-only as-of-feed scan. Week 6 is upcoming Oct 15-19 2026, prior week 5 may not be complete when snapshot taken. Historical lines are not verified contemporaneous DraftKings quotes.",
            "season_week_counts":counts,
            "all_positive_dual_edge_prior_games":[x for x in rows if x["week"]<through_week and x["both_edges_positive"]],
            "prior_2026_exact_flags":[x for x in rows if x["week"]<through_week and x["qualifies_full_flag"]],
            "week6_model_band_candidates":[x for x in rows if x["week"]==through_week and x["magnitude_025_049"]],
            "week6_full_flag_current_reference":[x for x in rows if x["week"]==through_week and x["qualifies_full_flag"]],
            "week6_full_slate":[x for x in rows if x["week"]==through_week]}

def main():
    games,stats=read_inputs()
    r=scan(games,stats)
    Path("nfl_home_field_week6_flag_scan.json").write_text(json.dumps(r,indent=2,allow_nan=False)+"\n")
    print("WEEK6_FLAG_BEGIN",flush=True)
    print(json.dumps(r,indent=2,allow_nan=False),flush=True)
    print("WEEK6_FLAG_END",flush=True)

if __name__=="__main__":
    main()
