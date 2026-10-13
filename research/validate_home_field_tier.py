"""Research-only validation audit for the proposed NFL Home Field Advantage tier.

Do not treat the 2019-2025 magnitude selection as out-of-sample evidence.
Rerunning this file does not change Sunday Slate's app or Elo model.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
from research.home_field_nfl_proposed import read_inputs, run, rate

MAG="0.25-0.49"
YEARS={"earlier_2019_2022":range(2019,2023),
       "later_2023_2025":range(2023,2026),
       "historical_2019_2025":range(2019,2026),
       "2026_diagnostic":(2026,)}

def wilson(w,n):
    if not n: return None
    z=1.95996398454
    p=w/n
    den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(100*(mid-half),2),round(100*(mid+half),2)]

def no_vig(h,a):
    """Reference historical two-sided home and away moneyline quotes."""
    if not (-500<float(h)<=-100 and float(a)>0): return None
    ph=(-float(h))/(100-float(h))
    pa=100/(100+float(a))
    return ph/(ph+pa)

def tail_prob(probs,wins):
    """Exact Poisson-binomial right tail under independent fair market forecasts."""
    pmf=np.zeros(len(probs)+1)
    pmf[0]=1.
    for i,p in enumerate(probs):
        pmf[1:i+2]=pmf[1:i+2]*(1-p)+pmf[:i+1]*p
        pmf[0]*=(1-p)
    return float(pmf[wins:].sum())

def detailed(rows):
    base=rate(rows)
    p=[no_vig(r["home_ml"],r["away_ml"]) for r in rows]
    assert all(a is not None for a in p)
    n=len(rows)
    base["95pct_su_wilson_pct"]=wilson(base["su_wins"],n)
    base["95pct_ats_wilson_pct"]=wilson(base["ats_wins"],base["ats_graded"])
    base["market_expected_su_wins"]=round(sum(p),2)
    base["market_no_vig_expected_win_pct"]=round(100*np.mean(p),2) if p else None
    base["one_sided_market_tail_p"]=round(tail_prob(p,base["su_wins"]),5) if p else None
    base["mean_price_am_american"]=round(float(np.mean([r["home_ml"] for r in rows])),1) if rows else None
    if n:
        # Fixed seed, nonparametric per-game resampling, retrospective only.
        returns=np.array([r["reference_profit"] for r in rows],dtype=float)
        rng=np.random.default_rng(20261012)
        b=[np.mean(rng.choice(returns,size=n,replace=True)) for _ in range(3000)]
        base["roi_bootstrap_95pct"]=list(map(lambda x:round(x*100,2),np.percentile(b,[2.5,97.5])))
        base["worse_10_cents_roi_pct"]=round(100*np.mean([
            100/abs(r["home_ml"]-10) if r["win"] else -1 for r in rows]),2)
        base["worse_20_cents_roi_pct"]=round(100*np.mean([
            100/abs(r["home_ml"]-20) if r["win"] else -1 for r in rows]),2)
    else:
        base["roi_bootstrap_95pct"]=None
        base["worse_10_cents_roi_pct"]=None
        base["worse_20_cents_roi_pct"]=None
    return base

def audit(records):
    focus=[r for r in records if r["magnitude_bucket"]==MAG]
    period={}
    for label,yrs in YEARS.items():
        sub=[r for r in focus if r["season"] in yrs]
        agree=[r for r in sub if r["elo_correct"]==r["win"]]
        disagree=[r for r in sub if r["elo_correct"]!=r["win"]]
        period[label]={"tier":detailed(sub),"elo_agrees":detailed(agree),"elo_disagrees":detailed(disagree),
                       "ats_wins_as_fraction_all":round(sum(r["ats_cover"] is True for r in sub)/len(sub),4) if sub else None}
    year={str(y):{"tier":detailed([r for r in focus if r["season"]==y]),
                  "elo_agree":rate([r for r in focus if r["season"]==y and r["elo_correct"]==r["win"]]),
                  "elo_disagree":rate([r for r in focus if r["season"]==y and r["elo_correct"]!=r["win"]])}
          for y in range(2019,2027)}
    return {"rule":"Home favorite, both positive standardized edges, magnitude [0.25,0.50), historic reference moneyline (-500,-100], minimum 3 previous full-stat games","phase":"Retrospectively selected on 2019-2025. 2026 is not prospective unless forecast and price were recorded before games.","period":period,"by_year":year,"current_2026_cases":[r for r in focus if r["season"]==2026]}

def main():
    games,stats=read_inputs()
    result=run(games,stats)
    validation=audit(result["records"])
    Path("nfl_home_field_tier_validation.json").write_text(json.dumps(validation,indent=2,allow_nan=False)+"\n")
    print("TIER_VALIDATION_BEGIN",flush=True)
    print(json.dumps(validation,indent=2,allow_nan=False),flush=True)
    print("TIER_VALIDATION_END",flush=True)
    games26=games[(games.season.eq(2026)) & games.home_score.notna() & games.away_score.notna()]
    print("FINAL_GAMES_2026_BY_WEEK:",games26.groupby("week").size().to_dict(),flush=True)

if __name__=="__main__":
    main()
