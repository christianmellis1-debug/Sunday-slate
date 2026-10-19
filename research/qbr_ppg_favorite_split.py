"""Market-favorite vs underdog study on the fixed 222 late-season QBR+PPG+Elo agreements."""
import json
from collections import defaultdict
from pathlib import Path
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
            "chosen_team":r["higher_qbr"],"opponent":r["away_team"] if r["higher_qbr"]==r["home_team"] else r["home_team"],
            "winning_team":r["winner"],
            "favorite_status":pos,"spread_bucket":group,
            "closing_spread_absolute":mag,
            "selected_score_margin":selected_margin,
            "won":r["winning_team"]==r["chosen_team"],"cover":cover,
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
    Path("qbr_ppg_favorite_split_2023_2025.json").write_text(json.dumps({"summary":summary,"games":full},indent=2))
    pd.DataFrame(full).to_csv("qbr_ppg_favorite_split_2023_2025.csv",index=False)
    compact={k:v for k,v in summary.items() if k not in ("underdog_winners","favorite_losses")}
    compact["underdog_winners"]=surprises
    print("FAVORITE_SPLIT_RESULTS_BEGIN")
    print(json.dumps(compact,indent=2))
    print("FAVORITE_SPLIT_RESULTS_END")


if __name__=="__main__":
    main()
