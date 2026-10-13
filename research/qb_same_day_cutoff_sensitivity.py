"""Sensitivity: last timestamped depth chart at T-2h before kickoff.

Never uses a snapshot at or after kickoff. Compares against the more
conservative 00:00 US/Eastern pre-gameday freeze in the base study.
"""
import bisect
import json
from pathlib import Path
import pandas as pd
from research import qb_pregame_availability_study as base

def cutoff_before_kickoff(weekly,dated,game,team):
    yr=int(game["season"])
    if yr<=2024:
        return ORIGINAL(weekly,dated,game,team)
    day=pd.Timestamp(game["gameday"])
    start=day.tz_localize("America/New_York").tz_convert("UTC")
    clock=str(game.get("gametime") or "")
    try:
        t=pd.Timestamp(f"{day.date()} {clock}")
        actual=t.tz_localize("America/New_York").tz_convert("UTC")
        cutoff=actual-pd.Timedelta(hours=2)
    except Exception:
        cutoff=start
    seq=dated.get((yr,base.norm(team)),[])
    idx=bisect.bisect_left(seq,(cutoff.value,""))-1
    if idx<0:return None,None,"no-prior-snapshot"
    stamp,gid=seq[idx]
    age=(cutoff.value-stamp)/86400e9
    if not 0<age<=base.MAX_DEPTH_AGE_DAYS:
        return None,round(age,1),"stale"
    return gid,round(age,2),"two-hours-pregame"

ORIGINAL=base.choose_asof
base.choose_asof=cutoff_before_kickoff

if __name__=="__main__":
    games=base.load_schedules()
    for col in ("season","week","home_score","away_score"):
        games[col]=pd.to_numeric(games[col],errors="coerce")
    boxes=base.load_qb_boxes()
    weekly,dated=base.load_depths()
    r=base.assess(games,boxes,weekly,dated)
    r["method"]["2025_2026_asof"]="last recorded timestamp at least 2 hours before scheduled kickoff, 14-day max age"
    compact={k:v for k,v in r.items() if k not in ("fitted",)}
    print("QB_T2H_BEGIN")
    print(json.dumps(compact,indent=2))
    print("QB_T2H_END")
    Path("qb_t2h_sensitivity_results.json").write_text(json.dumps(r,indent=2)+"\n")
