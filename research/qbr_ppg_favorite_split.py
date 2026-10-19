"""Market-favorite vs underdog study on the fixed 222 late-season QBR+PPG+Elo agreements."""
import json
from collections import defaultdict
from pathlib import Path
from math import comb, erfc, sqrt
import pandas as pd
from research.qbr_ppg_historical_validation import build, rating
from research.test_qbr_defense import load_games


def implied(price):
    if price is None or pd.isna(price):
        return None
    x = float(price)
    if x == 0:
        return None
    return 100 / (x + 100) if x > 0 else -x / (-x + 100)


def payoff(price, win):
    x = float(price)
    if x == 0:
        return None
    return (x / 100 if x > 0 else 100 / -x) if win else -1.0


def summarize(rs):
    n = len(rs)
    wins = sum(r["winning_team"] == r["chosen_team"] for r in rs)
    ats = [r["cover"] for r in rs if r["cover"] is not None]
    nats = len(ats)
    aw = sum(ats)
    money = [r for r in rs if r["chosen_moneyline"] is not None and
             r["chosen_implied_no_vig"] is not None]
    profits = sum(payoff(r["chosen_moneyline"], r["winning_team"] == r["chosen_team"]) for r in money)
    expected = sum(r["chosen_implied_no_vig"] for r in money)
    return {
        "games":n,"wins":wins,"losses":n-wins,
        "win_pct":round(100 * wins/n,2) if n else None,
        "covers":aw,"noncovers":nats-aw,"pushes":n-len(ats),
        "ats_pct":round(100*aw/nats,2) if nats else None,
        "priced_games":len(money),
        "average_no_vig_implied_win_pct":round(100*expected/len(money),2) if money else None,
        "observed_win_pct_same_priced_games":round(100*sum(r["winning_team"]==r["chosen_team"] for r in money)/len(money),2) if money else None,
        "net_units_flat_one_unit_stake":round(profits,3) if money else None,
        "roi_pct_at_reference_moneyline":round(100*profits/len(money),2) if money else None,
    }


def main():
    rows=build()
    cohort=[r for r in rows if r["season"] in (2023,2024,2025)
            and 7<=r["week"]<=18 and r["both_agree"]
            and r["elo"]==r["higher_qbr"]]
    assert len(cohort)==222, len(cohort)
    assert rating(cohort,"higher_qbr")["wins"]==166

    schedule=load_games()
    schedule=schedule[schedule.game_id.isin([r["game_id"] for r in cohort])]
    market={str(x.game_id): x for x in schedule.itertuples(index=False)}
    full=[]
    for r in cohort:
        g=market[r["game_id"]]
        line=r["spread_line"]
        if line is None:
            pos="spread_missing"
        elif abs(line)<1e-8:
            pos="pickem"
        elif r["higher_qbr"]==(r["home_team"] if line>0 else r["away_team"]):
            pos="favorite"
        else:
            pos="underdog"
        mag=abs(line) if line is not None else None
        group=(
            "spread missing" if mag is None else
            "Pick'em" if mag==0 else
            "0.5–2.5" if mag<3 else
            "3–6.5" if mag<7 else
            "7–9.5" if mag<10 else
            "10+"
        )
        away_ml=getattr(g,"away_moneyline",None)
        home_ml=getattr(g,"home_moneyline",None)
        ml = home_ml if r["higher_qbr"]==r["home_team"] else away_ml
        ml = float(ml) if ml is not None and pd.notna(ml) and float(ml)!=0 else None
        home_i,away_i=implied(home_ml),implied(away_ml)
        vig_sum=(home_i+away_i) if home_i is not None and away_i is not None else None
        prob=(home_i if r["higher_qbr"]==r["home_team"] else away_i) / vig_sum if vig_sum else None
        hm=r["home_score"]-r["away_score"]
        selected_margin=hm if r["higher_qbr"]==r["home_team"] else -hm
        spread_to_cover=((hm-line) if r["higher_qbr"]==r["home_team"] else (line-hm)) if line is not None else None
        cover=(spread_to_cover>0) if spread_to_cover is not None and abs(spread_to_cover)>1e-8 else None
        full.append({
            "season":r["season"],"week":r["week"],"game_id":r["game_id"],
            "chosen_team":r["higher_qbr"],"pick_venue":"home" if r["higher_qbr"]==r["home_team"] else "away","opponent":r["away_team"] if r["higher_qbr"]==r["home_team"] else r["home_team"],
            "winning_team":r["winner"],
            "favorite_status":pos,"spread_bucket":group,
            "closing_spread_absolute":mag,
            "selected_score_margin":selected_margin,
            "won":r["winner"]==r["higher_qbr"],"cover":cover,
            "chosen_moneyline":ml,"chosen_implied_no_vig":prob,
            "def_ppg_gap":r["ppg_gap"],"qbr_gap":r["qbr_gap"],
            "spread_line":line,
        })

    groups=defaultdict(list)
    for r in full:
        groups[r["favorite_status"]].append(r)
    years={}
    for y in (2023,2024,2025):
        years[str(y)]={s:summarize([r for r in full if r["season"]==y and r["favorite_status"]==s])
                       for s in ("favorite","underdog","pickem")}
    spread_buckets={}
    for p in ("favorite","underdog"):
        spread_buckets[p]={g:summarize([r for r in full if r["favorite_status"]==p and r["spread_bucket"]==g])
                           for g in ("0.5–2.5","3–6.5","7–9.5","10+")}
    winners=sorted([r for r in full if r["won"]],key=lambda r:(r["season"],r["week"],r["game_id"]))
    surprises=[r for r in full if r["favorite_status"]=="underdog" and r["won"]]
    losses=[r for r in full if r["favorite_status"]=="favorite" and not r["won"]]
    summary={
        "definition":"2023-2025 Weeks 7-18 Elo + prior-game ESPN QBR proxy + lower pregame scoring PPG all select same team. Market favorite/underdog from nflverse retrospective closing spread; spread_line positive means home favorite.",
        "overall":summarize(full),"market_status":{s:summarize(v) for s,v in groups.items()},
        "per_season":years,"spread_size":spread_buckets,
        "winners_favorite":sum(r["favorite_status"]=="favorite" for r in winners),
        "winners_underdog":sum(r["favorite_status"]=="underdog" for r in winners),
        "underdog_winners":surprises,
        "favorite_losses":losses,
    }
    # Focus only on favorite spreads 0.5–2.5 and 3–6.5.
    retained = [r for r in full
                if r["favorite_status"] == "favorite"
                and r["spread_bucket"] in ("0.5–2.5", "3–6.5")]
    focus = {
        "definition": "Predeclared shortlist: weeks 7–18 only, 2023–25, all three factors choose the SAME sportsbook favorite; 0.5–2.5 or 3–6.5 closing spread",
        "combined": summarize(retained),
        "two_bands": {},
        "year_by_band": {},
    }
    for band in ("0.5–2.5", "3–6.5"):
        subset = [r for r in retained if r["spread_bucket"] == band]
        focus["two_bands"][band] = summarize(subset)
        focus["year_by_band"][band] = {
            str(yr): summarize([r for r in subset if r["season"] == yr])
            for yr in (2023, 2024, 2025)
        }
    focus["per_year_combined"] = {
        str(yr): summarize([r for r in retained if r["season"] == yr])
        for yr in (2023, 2024, 2025)
    }
    focus["chosen_moneyline_ranges"] = {
        "near_even_-100_to_-139": summarize(
            [r for r in retained if r["chosen_moneyline"] is not None and -139 <= r["chosen_moneyline"] <= -100]),
        "moderate_-140_to_-199": summarize(
            [r for r in retained if r["chosen_moneyline"] is not None and -199 <= r["chosen_moneyline"] <= -140]),
        "heavier_-200_to_-299": summarize(
            [r for r in retained if r["chosen_moneyline"] is not None and -299 <= r["chosen_moneyline"] <= -200]),
        "very_heavy_-300_or_less": summarize(
            [r for r in retained if r["chosen_moneyline"] is not None and r["chosen_moneyline"] <= -300]),
    }
    # Important comparator: Elo-selected market favorites in the same spread band,
    # whether or not QB QBR + defensive PPG agree. Show exact data-coverage controls.
    all_market = {
        str(x.game_id): x
        for x in load_games().itertuples(index=False)
    }
    comparator = []
    for r in rows:
        if r["season"] not in (2023, 2024, 2025) or not (7 <= r["week"] <= 18):
            continue
        if r["winner"] == "TIE" or not r["elo"]:
            continue
        g = all_market.get(r["game_id"])
        if g is None:
            continue
        line = pd.to_numeric(getattr(g, "spread_line", None), errors="coerce")
        if pd.isna(line) or not (0 < abs(float(line)) < 7):
            continue
        fav = r["home_team"] if float(line) > 0 else r["away_team"]
        if r["elo"] != fav:
            continue
        band = "0.5–2.5" if abs(float(line)) < 3 else "3–6.5"
        home_ml = getattr(g, "home_moneyline", None)
        away_ml = getattr(g, "away_moneyline", None)
        target = home_ml if fav == r["home_team"] else away_ml
        target = float(target) if target is not None and pd.notna(target) and float(target) != 0 else None
        hi,ai = implied(home_ml),implied(away_ml)
        vig = hi + ai if hi is not None and ai is not None else None
        no_vig = (hi if fav == r["home_team"] else ai)/vig if vig else None
        home_margin = r["home_score"] - r["away_score"]
        cover_margin = home_margin - float(line) if fav == r["home_team"] else float(line) - home_margin
        comparator.append({
            "season": r["season"],"week":r["week"],"game_id":r["game_id"],
            "chosen_team":fav,"pick_venue":"home" if fav==r["home_team"] else "away","winning_team":r["winner"],
            "won":fav==r["winner"],"closing_spread_absolute":abs(float(line)),
            "spread_bucket":band,
            "chosen_moneyline":target,"chosen_implied_no_vig":no_vig,
            "cover":cover_margin > 0 if abs(cover_margin) > 1e-8 else None,
            "qbr_def_both_available":bool(r["higher_qbr"] and r["better_ppg"]),
            "triple_agree":bool(r["both_agree"] and r["higher_qbr"] == fav)
        })
    triple_reference=[r for r in comparator if r["triple_agree"]]
    if len(triple_reference)!=len(retained):
        raise RuntimeError(f"Comparator split mismatch {len(triple_reference)} vs {len(retained)}")
    focus["elo_favorite_control"] = {}
    for band in ("0.5–2.5", "3–6.5"):
        b=[r for r in comparator if r["spread_bucket"]==band]
        good=[r for r in b if r["qbr_def_both_available"]]
        t=[r for r in good if r["triple_agree"]]
        nt=[r for r in good if not r["triple_agree"]]
        focus["elo_favorite_control"][band]={
            "all_elo_favorites":summarize(b),
            "both_qbr_and_def_available":summarize(good),
            "triple_agree":summarize(t),
            "other_elo_favorites_same_stat_coverage":summarize(nt)
        }
    focus["elo_favorite_control"]["combined"] = {
        "all_elo_favorites":summarize(comparator),
        "both_qbr_and_def_available":summarize([r for r in comparator if r["qbr_def_both_available"]]),
        "triple_agree":summarize(triple_reference),
        "other_elo_favorites_same_stat_coverage":summarize([r for r in comparator if r["qbr_def_both_available"] and not r["triple_agree"]])
    }
    # Primary test: is home/away a reliable distinction within 3–6.5?
    # Two-sided Fisher exact uses observed W/L counts; no scipy dependency.
    def exact_fisher(home, away):
        a = sum(x["won"] for x in home)
        b = len(home)-a
        c = sum(x["won"] for x in away)
        d = len(away)-c
        n1=a+b; n2=c+d; total=n1+n2; success=a+c
        if min(n1,n2)==0:
            return None
        def p(x):
            return comb(success,x)*comb(total-success,n1-x)/comb(total,n1)
        observed=p(a)
        two_side=sum(
            p(x) for x in range(max(0,n1-(total-success)),min(success,n1)+1)
            if p(x)<=observed+1e-12)
        diff=a/n1-c/n2
        se=sqrt((a/n1)*(b/n1)/n1+(c/n2)*(d/n2)/n2)
        return {"home_wins":a,"home_losses":b,
                "road_wins":c,"road_losses":d,
                "home_minus_road_win_pct_points":round(diff*100,2),
                "fisher_two_sided_p":round(min(1.0,two_side),6),
                "normal_approx_95pct_difference_interval_pp":
                    [round((diff-1.96*se)*100,2),round((diff+1.96*se)*100,2)]}
    def compare_subset(rs):
        output = summarize(rs)
        prices=[x["chosen_implied_no_vig"] for x in rs if x["chosen_implied_no_vig"] is not None]
        wins=[int(x["won"]) for x in rs if x["chosen_implied_no_vig"] is not None]
        if prices:
            gap=(sum(wins)-sum(prices))/len(prices)
            v=sum(x*(1-x) for x in prices)
            z=(sum(wins)-sum(prices))/sqrt(v) if v>0 else None
            output["observed_minus_no_vig_implied_pp"]=round(gap*100,2)
            output["normal_approx_two_sided_p_vs_no_vig"]=round(erfc(abs(z)/sqrt(2)),5) if z is not None else None
        output["avg_absolute_spread"]=round(sum(x["closing_spread_absolute"] for x in rs)/len(rs),3) if rs else None
        return output
    comparisons={}
    for band in ("3–6.5", "0.5–2.5", "combined"):
        selected=[r for r in retained if band=="combined" or r["spread_bucket"]==band]
        home=[r for r in selected if r["pick_venue"]=="home"]
        away=[r for r in selected if r["pick_venue"]=="away"]
        controls=[r for r in comparator if (band=="combined" or r["spread_bucket"]==band) and r["qbr_def_both_available"]]
        other=[r for r in controls if not r["triple_agree"]]
        def venue_rows(rr):
            return {v:compare_subset([r for r in rr if r["pick_venue"]==v])
                    for v in ("home","away")}
        comparisons[band]={
            "triple_agreement":venue_rows(selected),
            "fisher_home_vs_road":exact_fisher(home,away),
            "year_by_venue":{
                str(year):venue_rows([r for r in selected if r["season"]==year])
                for year in (2023,2024,2025)
            },
            "elo_other_picks_with_same_qbr_ppg_coverage":venue_rows(other),
            "elo_all_picks_with_same_qbr_ppg_coverage":venue_rows(controls)
        }
    focus["home_away"] = comparisons
    print("HOME_AWAY_PRIMARY_RESEARCH_BEGIN")
    print(json.dumps(comparisons,indent=2,allow_nan=False))
    print("HOME_AWAY_PRIMARY_RESEARCH_END")
    summary["focus_under_7"] = focus
    print("FOCUS_UNDER_7_BEGIN")
    print(json.dumps(focus,indent=2,allow_nan=False))
    print("FOCUS_UNDER_7_END")

    Path("qbr_ppg_favorite_split_2023_2025.json").write_text(json.dumps({"summary":summary,"games":full},indent=2))
    pd.DataFrame(full).to_csv("qbr_ppg_favorite_split_2023_2025.csv",index=False)
    compact={k:v for k,v in summary.items() if k not in ("underdog_winners","favorite_losses")}
    compact["underdog_winners"]=surprises
    print("FAVORITE_SPLIT_RESULTS_BEGIN")
    print(json.dumps(compact,indent=2))
    print("FAVORITE_SPLIT_RESULTS_END")


if __name__=="__main__":
    main()
