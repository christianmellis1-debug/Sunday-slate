"""Sunday Slate: historical validation of higher pregame QBR + fewer points allowed.

The primary QB treatment matches the 2026 research audit: choose the most-used
QB from the target game retrospectively and compute their season-to-date
plays-weighted weekly ESPN QBR from ONLY earlier games. This has retrospective
starter-selection bias. A fully pregame QB-leader sensitivity (prior-play leader)
is also reported. Defense is previous same-season points allowed / game.

NO changes to production predictions. No use of final-season team ratings.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from research.test_qbr_defense import load_games, load_qbr, normalized
from sunday_slate.model import predict_regular_season

YEARS = (2023, 2024, 2025, 2026)
YEARS_HIST = (2023, 2024, 2025)


def rating(records, pick_key):
    n = len(records)
    w = sum(x[pick_key] == x["winner"] for x in records)
    return {"n": n, "wins": w, "losses": n-w, "pct": round(100*w/n, 2) if n else None}


def metric(records, pick_key):
    valid = [x for x in records if x.get(pick_key) and x["winner"] != "TIE"]
    return rating(valid, pick_key)


def build():
    games = load_games()
    qbr = load_qbr()
    qbr = qbr[qbr.season.isin(YEARS)].copy()
    g = games[(games.season.isin(YEARS)) & (games.week >= 1) &
              (games.home_score.notna()) & (games.away_score.notna())].copy()
    g = g.sort_values(["season", "week", "game_id"], kind="stable")
    elo = predict_regular_season(games)
    if elo.game_id.duplicated().any():
        raise RuntimeError("Duplicate Elo game_id")
    elo_pick = dict(zip(elo.game_id.astype(str), elo.predicted_winner.astype(str)))

    # Target-game QB retrospective label; prior-to-game QBR only.
    game_qb = {}
    for (season, week, team), group in qbr.groupby(["season", "week_num", "team_abb"]):
        best = group.sort_values(["qb_plays", "player_id"], ascending=[False, True]).iloc[0]
        game_qb[(int(season), int(week), str(team))] = str(best.player_id)

    # Previously accumulated QB and defensive histories; never update mid-week.
    rows = []
    for season, season_games in g.groupby("season", sort=True):
        season = int(season)
        pre_qbs = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        allowed = defaultdict(lambda: [0.0, 0])
        qb_year = qbr[qbr.season.eq(season)]
        qb_week_records = defaultdict(list)
        for r in qb_year.itertuples(index=False):
            qb_week_records[int(r.week_num)].append(r)
        for week, slate in season_games.groupby("week", sort=True):
            week = int(week)
            if week >= 2:
                def pre_qbr(team, qb_id):
                    p = pre_qbs[team].get(str(qb_id))
                    if not p or p[1] < 30:
                        return None
                    return p[0]/p[1]

                def historic_leader(team):
                    previous = [(data[1], pid) for pid, data in pre_qbs[team].items()
                                if data[1] >= 30]
                    if not previous:
                        return None
                    return sorted(previous, key=lambda x: (-x[0], str(x[1])))[0][1]

                for match in slate.itertuples(index=False):
                    home, away = normalized(match.home_team), normalized(match.away_team)
                    winner = ("TIE" if float(match.home_score) == float(match.away_score)
                              else home if float(match.home_score) > float(match.away_score) else away)
                    hq_id = game_qb.get((season, week, home))
                    aq_id = game_qb.get((season, week, away))
                    hq, aq = (pre_qbr(home, hq_id) if hq_id else None,
                              pre_qbr(away, aq_id) if aq_id else None)
                    qpick = (home if hq > aq else away if aq > hq else None) if hq is not None and aq is not None else None
                    hd = allowed[home][0]/allowed[home][1] if allowed[home][1] else None
                    ad = allowed[away][0]/allowed[away][1] if allowed[away][1] else None
                    dpick = (home if hd < ad else away if ad < hd else None) if hd is not None and ad is not None else None
                    hp_lead, ap_lead = historic_leader(home), historic_leader(away)
                    hl, al = (pre_qbr(home, hp_lead) if hp_lead else None,
                              pre_qbr(away, ap_lead) if ap_lead else None)
                    pre_pick = (home if hl > al else away if al > hl else None) if hl is not None and al is not None else None
                    spread = pd.to_numeric(getattr(match, "spread_line", None), errors="coerce")
                    spread = float(spread) if pd.notna(spread) else None
                    rows.append({
                        "season": season, "week": week, "game_id": str(match.game_id),
                        "home_team": home, "away_team": away,
                        "home_score": int(match.home_score), "away_score": int(match.away_score),
                        "winner": winner, "home_qbr": round(hq, 4) if hq is not None else None,
                        "away_qbr": round(aq, 4) if aq is not None else None,
                        "higher_qbr": qpick, "better_ppg": dpick,
                        "home_ppg_allowed": round(hd, 3) if hd is not None else None,
                        "away_ppg_allowed": round(ad, 3) if ad is not None else None,
                        "qbr_gap": abs(hq-aq) if hq is not None and aq is not None else None,
                        "ppg_gap": abs(hd-ad) if hd is not None and ad is not None else None,
                        "home_def_games": allowed[home][1], "away_def_games": allowed[away][1],
                        "both_agree": bool(qpick and dpick and qpick == dpick and winner != "TIE"),
                        "preweek_qb_leader_pick": pre_pick,
                        "preweek_leader_and_def_agree": bool(pre_pick and dpick and pre_pick == dpick and winner != "TIE"),
                        "same_qb_by_prior_plays": hp_lead == hq_id and ap_lead == aq_id,
                        "elo": elo_pick.get(str(match.game_id)),
                        "spread_line": spread
                    })
            # Freeze week: update only AFTER scoring every game for this week.
            for match in slate.itertuples(index=False):
                home, away = normalized(match.home_team), normalized(match.away_team)
                allowed[home][0] += float(match.away_score)
                allowed[home][1] += 1
                allowed[away][0] += float(match.home_score)
                allowed[away][1] += 1
            for q in qb_week_records[week]:
                team = str(q.team_abb)
                qb_id = str(q.player_id)
                rec = pre_qbs[team][qb_id]
                rec[0] += float(q.qbr_total) * float(q.qb_plays)
                rec[1] += float(q.qb_plays)

    return rows


def describe(rows):
    all_decisive = [r for r in rows if r["winner"] != "TIE"]
    qb = [r for r in all_decisive if r["higher_qbr"]]
    defense = [r for r in all_decisive if r["better_ppg"]]
    both_available = [r for r in qb if r["better_ppg"]]
    agreement = [r for r in both_available if r["both_agree"]]
    conflicts = [r for r in both_available if not r["both_agree"]]
    elo_compatible = [r for r in agreement if r["elo"]]
    elo_matches = [r for r in elo_compatible if r["elo"] == r["higher_qbr"]]
    elo_disagrees = [r for r in elo_compatible if r["elo"] != r["higher_qbr"]]
    preweek_leader = [r for r in all_decisive if r["preweek_leader_and_def_agree"]]
    stable_qb = [r for r in agreement if r["same_qb_by_prior_plays"]]
    return {
        "total_decisive_games": len(all_decisive),
        "qbr_eligible": metric(all_decisive, "higher_qbr"),
        "defense_eligible": metric(all_decisive, "better_ppg"),
        "both_available_games": len(both_available),
        "agreement": rating(agreement, "higher_qbr"),
        "elo_on_agreement": metric(agreement, "elo"),
        "elo_agrees_with_combo": {"combo": rating(elo_matches, "higher_qbr"),
                                  "elo": rating(elo_matches, "elo")},
        "elo_disagrees_with_combo": {"combo": rating(elo_disagrees, "higher_qbr"),
                                     "elo": rating(elo_disagrees, "elo")},
        "conflicts": {"qbr": rating(conflicts, "higher_qbr"),
                      "defense": rating(conflicts, "better_ppg"),
                      "elo": metric(conflicts, "elo")},
        "only_previous_week_QB_usage": {"combo":rating(preweek_leader, "preweek_qb_leader_pick"),
                                        "elo":metric(preweek_leader, "elo"),
                                        "n":len(preweek_leader)},
        "actual_QB_same_as_previous_usage_leader": {"combo":rating(stable_qb, "higher_qbr"),
                                                    "elo":metric(stable_qb, "elo"),
                                                    "n":len(stable_qb)},
        "agreement_game_count": len(agreement),
        "qbr_defense_agreement_pct": round(100*len(agreement)/len(both_available),2) if both_available else None,
    }


def summarize(rows):
    hist = [r for r in rows if r["season"] <= 2025]
    target = [r for r in rows if r["season"] == 2026 and r["week"] <= 6]
    summary = {
        "definitions": {
            "QBR": "season-to-date prior weeks' QB-plays-weighted ESPN Total QBR (>=30 plays), QB selected by most game-week plays retrospectively; NOT ESPN cumulative composite and NOT independently verified pregame starter",
            "QBR_sensitivity": "team's most-used QB from prior weeks only, prior 30+ QB plays; avoids retrospective QB selection but not guaranteed starter",
            "defense": "same-season opponent points allowed divided by completed games BEFORE target week; fewer is better",
            "seasons": "2023-2025 full season, 2026 weeks 2-6, no week 1, no ties",
            "market": "nflverse game spread_line is reference closing line; not verified as quote executable before kickoff; ATS is diagnostic only",
        },
        "year": {str(yr): describe([r for r in rows if r["season"] == yr and (yr != 2026 or r["week"]<=6)]) for yr in YEARS},
        "historical_full_2023_2025": describe(hist),
        "historical_early_weeks2_6": describe([r for r in hist if r["week"]<=6]),
        "historical_later_weeks7_18": describe([r for r in hist if r["week"]>=7]),
        "current_2026_weeks2_6": describe(target),
        "year_early_weeks2_6": {str(yr):describe([r for r in rows if r["season"] == yr and r["week"]<=6]) for yr in YEARS},
        "week_2026": {str(w):describe([r for r in target if r["week"]==w]) for w in range(2,7)},
    }

    groups = {
        "hist_early": [r for r in hist if r["week"]<=6],
        "hist_full": hist,
        "2026_early": target,
        "all_early": [r for r in rows if r["week"]<=6 and r["season"] in YEARS]
    }
    stratified={}
    for name, cohort in groups.items():
        matched = [r for r in cohort if r["both_agree"]]
        report={"qbr_gap_buckets":[], "defense_gap_buckets":[], "prior_game_minimums":[],
                "threshold_screen":[], "home_away":[], "spread":{}}
        for lo,hi in ((0,5),(5,10),(10,20),(20,None)):
            sub = [r for r in matched if r["qbr_gap"]>=lo and (hi is None or r["qbr_gap"]<hi)]
            report["qbr_gap_buckets"].append({"range":[lo,hi],"combo":rating(sub,"higher_qbr"),"elo":metric(sub,"elo")})
        for lo,hi in ((0,3),(3,7),(7,None)):
            sub = [r for r in matched if r["ppg_gap"]>=lo and (hi is None or r["ppg_gap"]<hi)]
            report["defense_gap_buckets"].append({"range":[lo,hi],"combo":rating(sub,"higher_qbr"),"elo":metric(sub,"elo")})
        for num in (1,2,3,4,5):
            sub = [r for r in matched if min(r["home_def_games"],r["away_def_games"])>=num]
            report["prior_game_minimums"].append({"n_prior":num,"combo":rating(sub,"higher_qbr"),"elo":metric(sub,"elo")})
        for qgap,dgap in ((0,0),(5,0),(10,0),(20,0),(0,3),(0,7),(5,3),(10,3),(5,7),(10,7)):
            sub = [r for r in matched if r["qbr_gap"]>=qgap and r["ppg_gap"]>=dgap]
            opposite=[r for r in sub if r["elo"]!=r["higher_qbr"]]
            report["threshold_screen"].append({
                "min_qbr":qgap,"min_def_ppg_gap":dgap,
                "combo":rating(sub,"higher_qbr"),"elo":metric(sub,"elo"),
                "combo_when_elo_disagrees":rating(opposite,"higher_qbr"),
            })
        for loc in ("home","away"):
            sub = [r for r in matched if r["higher_qbr"]==r[loc+"_team"]]
            report["home_away"].append({"selection":loc,"combo":rating(sub,"higher_qbr"),"elo":metric(sub,"elo")})
        market=[r for r in matched if r["spread_line"] is not None]
        spread_margin=[]
        ats_w=ats_l=ats_push=0
        underdog=favorite=0
        favor_win=favor_loss=und_win=und_loss=0
        for r in market:
            line=r["spread_line"]
            if line!=0:
                fav=r["home_team"] if line>0 else r["away_team"]
                if r["higher_qbr"]==fav:
                    favorite+=1
                    favor_win += int(r["higher_qbr"] == r["winner"])
                    favor_loss += int(r["higher_qbr"] != r["winner"])
                else:
                    underdog+=1
                    und_win += int(r["higher_qbr"] == r["winner"])
                    und_loss += int(r["higher_qbr"] != r["winner"])
            home_margin=r["home_score"]-r["away_score"]
            v=home_margin-line if r["higher_qbr"]==r["home_team"] else line-home_margin
            if abs(v)<1e-8:ats_push+=1
            elif v>0:ats_w+=1
            else:ats_l+=1
        report["spread"]={
            "has_closing_spread":len(market),"ats_w":ats_w,"ats_l":ats_l,"ats_push":ats_push,
            "ats_pct_excluding_push":round(100*ats_w/(ats_w+ats_l),2) if ats_w+ats_l else None,
            "favorites_n":favorite,"favorites_record":[favor_win,favor_loss],
            "underdogs_n":underdog,"underdogs_record":[und_win,und_loss],
        }
        stratified[name]=report
    summary["breakdowns"]=stratified
    return summary


def main():
    rows=build()
    summary=summarize(rows)
    cohort=[r for r in rows if r["season"]==2026 and r["week"]<=6 and r["both_agree"]]
    if len(cohort)!=29 or rating(cohort,"higher_qbr")["wins"]!=20:
        raise RuntimeError("Previous 2026 Weeks 2-6 QBR + defense record not reproduced "
                           +repr(rating(cohort,"higher_qbr")))
    if sum(r["winner"]!="TIE" and r["higher_qbr"] is not None for r in rows
           if r["season"]==2026 and r["week"]<=6) !=63:
        raise RuntimeError("Previous 2026 QBR cohort not reproduced")
    Path("qbr_ppg_historical_validation.json").write_text(
        json.dumps({"summary":summary,"games":rows},indent=2,allow_nan=False)+"\n")
    pd.DataFrame(rows).to_csv("qbr_ppg_historical_validation.csv",index=False)
    print("QBR_PPG_HISTORICAL_SUMMARY_BEGIN",flush=True)
    print(json.dumps(summary,indent=2,allow_nan=False),flush=True)
    print("QBR_PPG_HISTORICAL_SUMMARY_END",flush=True)


if __name__=="__main__":
    main()
