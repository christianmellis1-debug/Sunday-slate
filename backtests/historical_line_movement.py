"""Reproducible, outcome-graded NFL opening-to-closing spread movement backtest.

Source: ESPN NFL scoreboard results and ESPN Core per-game bookmaker odds.
2024 uses ESPN BET (58); 2025 and 2026 use DraftKings (100).
Do not substitute an opening-line proxy, a different sportsbook, or postgame scores.
This research does not change Sunday Slate predictions.
"""
from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from collections import defaultdict
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events"
OUTPUT = Path("backtests/output")
PROVIDERS = {2024: ("58", "ESPN BET"), 2025: ("100", "DraftKings"), 2026: ("100", "DraftKings")}
WEEKS = {2024: range(1, 19), 2025: range(1, 19), 2026: range(1, 7)}
MAX_WORKERS = 12


def get(url):
    request = Request(url, headers={"User-Agent":"Mozilla/5.0 SundaySlateResearch/1.0",
                                    "Accept":"application/json"})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=16) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if attempt == 0 and exc.code in (429, 500, 502, 503, 504):
                time.sleep(1)
                continue
            raise
        except (OSError, ValueError):
            if attempt == 0:
                time.sleep(0.2)
                continue
            raise


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
        if not math.isfinite(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


def spread_value(odds, side, phase):
    v = (odds.get(side, {}).get(phase, {}).get("pointSpread", {}))
    n = number(v.get("american") or v.get("alternateDisplayValue"))
    if n is None or abs(n) > 30 or n * 2 != int(n * 2):
        return None
    return n


def parse_result(event, season, week):
    comps = event.get("competitions") or []
    if len(comps) != 1:
        return None
    comp = comps[0]
    status = (comp.get("status") or {}).get("type") or {}
    if not status.get("completed") or status.get("state") != "post":
        return None
    teams = {x.get("homeAway"):x for x in comp.get("competitors", [])}
    if set(teams) != {"home","away"}:
        return None
    home,away=teams["home"],teams["away"]
    try:
        hs=int(home["score"])
        aws=int(away["score"])
    except (KeyError,TypeError,ValueError):
        return None
    if hs < 0 or aws < 0:
        return None
    comp_id = str(comp.get("id") or event.get("id") or "")
    if not comp_id.isdigit():
        return None
    return {"season":season, "week":week,"event_id":str(event.get("id")),
            "comp_id":comp_id, "date":event.get("date") or comp.get("date"),
            "home_team":home.get("team",{}).get("abbreviation",""),
            "away_team":away.get("team",{}).get("abbreviation",""),
            "home_score":hs, "away_score":aws}


def load_events():
    games=[]
    audit=defaultdict(lambda: {"events":0,"final_games":0,"scoreboard_errors":0})
    for season, weeks in WEEKS.items():
        for week in weeks:
            key=str(season)
            try:
                payload=get(f"{BASE}?dates={season}&seasontype=2&week={week}&limit=100")
            except Exception as exc:
                audit[key]["scoreboard_errors"]+=1
                print("SCOREBOARD_ERROR",season,week,type(exc).__name__,str(exc)[:80])
                continue
            events=(payload or {}).get("events",[])
            audit[key]["events"]+=len(events)
            for event in events:
                game=parse_result(event,season,week)
                if game:
                    audit[key]["final_games"]+=1
                    games.append(game)
    unique={}
    for game in games:
        unique[game["event_id"]]=game
    return list(unique.values()),audit


def fetch_odds(game):
    season=game["season"]
    provider_id,provider_name=PROVIDERS[season]
    endpoint=f"{CORE}/{game['event_id']}/competitions/{game['comp_id']}/odds/{provider_id}"
    try:
        odds=get(endpoint)
    except Exception as exc:
        return None, f"FETCH_{type(exc).__name__}"
    if not odds:
        return None, "NOT_PUBLISHED"
    provider=(odds.get("provider") or {})
    if str(provider.get("id")) != provider_id or str(provider.get("name","")).casefold()!=provider_name.casefold():
        return None,"BOOK_MISMATCH"
    a,h="awayTeamOdds","homeTeamOdds"
    away_open=spread_value(odds,a,"open")
    away_close=spread_value(odds,a,"close")
    home_open=spread_value(odds,h,"open")
    home_close=spread_value(odds,h,"close")
    if None in (away_open,away_close,home_open,home_close):
        return None,"MISSING_OPEN_CLOSE"
    if abs(away_open+home_open)>0.001 or abs(away_close+home_close)>0.001:
        return None,"INCONSISTENT_LINES"
    delta=round(home_close-home_open,4)
    magnitude=abs(delta)
    moved="home" if delta < -0.001 else "away" if delta > 0.001 else "none"
    row={**game,"provider":provider_name,
         "home_open":home_open,"home_close":home_close,"away_open":away_open,"away_close":away_close,
         "spread_shift":delta,"magnitude":magnitude,"moved_side":moved}
    margin = game["home_score"]-game["away_score"]
    # For the moved-toward team, use that team's score margin + its signed spread.
    if moved=="none":
        row.update(su_result="",ats_open="",ats_close="",moved_team="",moved_open_role="")
    else:
        moved_margin = margin if moved=="home" else -margin
        moved_open = home_open if moved=="home" else away_open
        moved_close = home_close if moved=="home" else away_close
        row["moved_team"]=game["home_team"] if moved=="home" else game["away_team"]
        row["moved_open_role"]="Underdog" if moved_open>0 else "Favorite" if moved_open<0 else "Pick'em"
        row["su_result"]="W" if moved_margin>0 else "L" if moved_margin<0 else "P"
        for key,spread in (("ats_open",moved_open),("ats_close",moved_close)):
            value = moved_margin+spread
            row[key]="W" if value>0 else "L" if value<0 else "P"
    return row,None


def counts(rows,col):
    wins=sum(x.get(col)=="W" for x in rows)
    losses=sum(x.get(col)=="L" for x in rows)
    pushes=sum(x.get(col)=="P" for x in rows)
    pct=round(100*wins/(wins+losses),1) if wins+losses else None
    return {"wins":wins,"losses":losses,"pushes":pushes,"win_pct_ex_push":pct}


def summarize(rows):
    return {"games":len(rows),"su":counts(rows,"su_result"),
            "ats_at_open":counts(rows,"ats_open"),
            "ats_at_close":counts(rows,"ats_close")}


def bucket(row):
    m=row["magnitude"]
    if m==0:return "No spread change"
    if m<1:return "0.5 point"
    if m<1.5:return "1 point"
    if m<3:return "1.5–2.5 points"
    return "3+ points"


def group(rows,keyfn):
    found=defaultdict(list)
    for row in rows:
        found[keyfn(row)].append(row)
    return {k:summarize(v) for k,v in sorted(found.items())}


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    games,audit=load_events()
    print(f"Retrieved {len(games)} completed regular-season games.")
    rows=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs={pool.submit(fetch_odds,game):game for game in games}
        for task in as_completed(jobs):
            game=jobs[task]
            season=str(game["season"])
            try:
                row,error=task.result()
            except Exception as exc:
                row,error=None,"EXCEPTION_"+type(exc).__name__
            if error:
                errors=audit[season].setdefault("odds_failures",{})
                errors[error]=errors.get(error,0)+1
            elif row is not None:
                rows.append(row)
    rows.sort(key=lambda x:(x["season"],x["week"],x["date"],x["event_id"]))
    for row in rows:
        audit[str(row["season"])]["valid_odds_games"]=audit[str(row["season"])].get("valid_odds_games",0)+1
        if row["magnitude"] > 0:
            audit[str(row["season"])]["moved_games"]=audit[str(row["season"])].get("moved_games",0)+1

    moved=[r for r in rows if r["magnitude"]>0]
    summary={
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "seasons":[2024,2025,2026],"stage":"regular season only",
        "source":"ESPN Core odds open/close + ESPN scoreboard final scores",
        "providers":{str(s):name for s,(_,name) in PROVIDERS.items()},
        "caution":"2024 ESPN BET and 2025-2026 DraftKings are separate sportsbook cohorts; pooled metrics mix bookmakers. No retrospective exact quote timestamps or proof of executable open/close prices.",
        "audit":dict(audit),
        "all_valid_odds_games":len(rows),
        "all_spread_movers":len(moved),
        "moved_summary_all_books":summarize(moved),
        "by_season":group(moved,lambda x:str(x["season"])),
        "by_magnitude_all_books":group(moved,bucket),
        "by_magnitude_2025_2026_draftkings":group([r for r in moved if r["provider"]=="DraftKings"],bucket),
        "by_season_magnitude":group(moved,lambda x:f"{x['season']} | {bucket(x)}"),
        "by_provider":group(moved,lambda x:x["provider"]),
        "by_open_role":group(moved,lambda x:x["moved_open_role"]),
        "by_moved_side":group(moved,lambda x:x["moved_side"]),
        "by_week_2026":group([r for r in moved if r["season"]==2026],lambda x:f"Week {x['week']}"),
        "big_movers":[r for r in moved if r["magnitude"]>=3],
    }
    (OUTPUT/"historical_line_movement_summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n")
    if rows:
        with (OUTPUT/"historical_line_movement_games.csv").open("w",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    md=["# NFL opening-to-closing spread movement backtest","",
        "2024: ESPN BET. 2025–2026 (completed weeks 1–6): DraftKings.",
        "Only regular-season final games with complete and internally consistent same-book opening/closing spreads are included.",
        "The movement side is whichever team saw its signed spread decrease, making the market more favorable to it.",
        "SU means outright wins; ATS is separately calculated against opening and closing spreads; pushes are excluded from percentages.",
        "Source: ESPN scoreboards and ESPN Core odds. This is independent of Sunday Slate's Elo model.",""]
    for key in ("by_season","by_magnitude_2025_2026_draftkings","by_magnitude_all_books","by_open_role"):
        md.extend(["## "+key.replace("_"," "), "| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |",
                   "|---|---:|---|---|---|"])
        for label,record in summary[key].items():
            def fmt(k):
                x=record[k]
                return f"{x['wins']}-{x['losses']}-{x['pushes']} ({x['win_pct_ex_push']}%)"
            md.append(f"| {label} | {record['games']} | {fmt('su')} | {fmt('ats_at_open')} | {fmt('ats_at_close')} |")
        md.append("")
    md.append("## Audit and limitations")
    md.append("Same-book prices only. Books and seasons must not be mistaken for equivalent populations.")
    md.append("ESPN's stored open/close fields have no independent observation timestamps; opening prices differ across books.")
    md.append("Opening ATS cover rates can be mechanically better than closing ATS when the market moves toward a team.")
    md.append("The test does not validate real-time odds availability, bet execution, or profitability.")
    md.append("Uncovered games and provider/API failures are excluded; consult summary JSON audit.")
    (OUTPUT/"historical_line_movement_report.md").write_text("\n".join(md)+"\n")
    print(json.dumps({"eligible":len(rows),"movers":len(moved),"audit":dict(audit),
                      "by_season":summary["by_season"],
                      "by_magnitude_DK":summary["by_magnitude_2025_2026_draftkings"]},indent=2))


if __name__=="__main__":
    main()
