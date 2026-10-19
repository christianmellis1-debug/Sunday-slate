"""2026 season-to-date QBR + defense EPA agreement; reproducible, research only.

EPA allowed/play = opponents' total pass EPA + rush EPA divided by opponents'
pass attempts + rush carries, from prior completed NFL weekly box aggregates.
This is a team box-based EPA approximation, NOT a full PBP EPA model.
Week 1 uses last season's defensive baseline. Other games use current-season
prior weeks only, with all features frozen before the whole slate.
Same QBR leading-game-passer proxy as the original 77-game audit.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from research.test_qbr_defense import load_games, load_qbr, normalized
from sunday_slate.model import predict_regular_season


def state():
    return defaultdict(lambda: {"epa": 0.0, "plays": 0.0, "games": 0, "points": 0.0})


def measure(rows, key):
    n = len(rows)
    wins = sum(r[key] is True for r in rows)
    return {"games": n, "wins": wins, "losses": n - wins,
            "win_pct": round(100 * wins / n, 2) if n else None}


def get_epa_stat_rows():
    import nflreadpy
    stats = pd.DataFrame(nflreadpy.load_team_stats(
        seasons=[2025, 2026], summary_level="week").to_dicts())
    required = {"season", "week", "game_id", "team", "opponent_team",
                "season_type", "passing_epa", "rushing_epa", "attempts", "carries"}
    if not required.issubset(stats):
        raise RuntimeError("Team EPA data missing " + repr(sorted(required - set(stats))))
    stats = stats[stats["season_type"].eq("REG")].copy()
    for field in ("season", "week", "passing_epa", "rushing_epa", "attempts", "carries"):
        stats[field] = pd.to_numeric(stats[field], errors="coerce")
    stats["team"] = stats["team"].map(normalized)
    stats["opponent_team"] = stats["opponent_team"].map(normalized)
    stats = stats[stats["season"].isin([2025, 2026])].copy()
    stats["epa"] = stats["passing_epa"] + stats["rushing_epa"]
    stats["plays"] = stats["attempts"] + stats["carries"]
    stats = stats[stats["epa"].notna() & stats["plays"].gt(0)].copy()
    if stats.duplicated(["game_id", "team"]).any():
        raise RuntimeError("Ambiguous duplicates in team EPA data")
    return stats.set_index(["game_id", "team"])


def add_week_to_state(games, boxes, rates):
    """Update state after a slate; skip incomplete/mismatched box pairs."""
    matched = 0
    for g in games.itertuples(index=False):
        if pd.isna(g.home_score) or pd.isna(g.away_score):
            continue
        h, a = normalized(g.home_team), normalized(g.away_team)
        if (g.game_id, h) not in boxes.index or (g.game_id, a) not in boxes.index:
            continue
        own, opp = boxes.loc[(g.game_id, h)], boxes.loc[(g.game_id, a)]
        if not (str(own.opponent_team) == a and str(opp.opponent_team) == h
                and int(own.season) == int(g.season) and int(opp.season) == int(g.season)
                and int(own.week) == int(g.week) and int(opp.week) == int(g.week)):
            raise RuntimeError(f"Team/opponent EPA box mismatch {g.game_id}")
        matched += 1
        for team, defense_against in ((h, opp), (a, own)):
            p = rates[team]
            p["epa"] += float(defense_against.epa)
            p["plays"] += float(defense_against.plays)
            p["games"] += 1
            p["points"] += float(g.away_score if team == h else g.home_score)
    return matched


def defense_rate(s, team, kind="epa"):
    v = s[team]
    denom = v["plays"] if kind == "epa" else v["games"]
    return v[kind] / denom if v["games"] >= 1 and denom > 0 else None


def main():
    games = load_games()
    qb = load_qbr()
    qb = qb[qb.season.isin([2025, 2026])]
    q2026 = qb[qb.season.eq(2026)]
    boxes = get_epa_stat_rows()
    chosen_qbs = {}
    for (week, team), group in q2026.groupby(["week_num", "team_abb"]):
        r = group.sort_values("qb_plays", ascending=False).iloc[0]
        chosen_qbs[(int(week), str(team))] = str(r.player_id)

    def pregame_qbr(pid, week):
        year = 2025 if week == 1 else 2026
        data = qb[(qb.season == year) & qb.player_id.astype(str).eq(str(pid))]
        if week > 1:
            data = data[data.week_num.lt(week)]
        plays = float(data.qb_plays.sum())
        return (float((data.qbr_total * data.qb_plays).sum() / plays)
                if plays >= 30 else None)

    season25 = games[games.season.eq(2025) & games.home_score.notna()
                     & games.away_score.notna()].copy()
    season26 = games[games.season.eq(2026) & games.week.le(6)
                     & games.home_score.notna() & games.away_score.notna()].copy()
    season26 = season26.sort_values(["week", "game_id"], kind="stable")
    p25 = state()
    p26 = state()
    prev_year_games = add_week_to_state(season25, boxes, p25)
    if prev_year_games < 250:
        raise RuntimeError(f"Insufficient 2025 EPA box coverage: {prev_year_games} games")

    elo = predict_regular_season(games)
    elo_picks = dict(zip(elo.game_id.astype(str), elo.predicted_winner.astype(str)))
    rows = []
    matched_2026 = 0
    for week, slate in season26.groupby("week", sort=True):
        week = int(week)
        defense_state = p25 if week == 1 else p26
        for g in slate.itertuples(index=False):
            h, a = normalized(g.home_team), normalized(g.away_team)
            hpid, apid = chosen_qbs.get((week, h)), chosen_qbs.get((week, a))
            hq = pregame_qbr(hpid, week) if hpid else None
            aq = pregame_qbr(apid, week) if apid else None
            selected = (h if hq > aq else a) if hq is not None and aq is not None and hq != aq else None
            he, ae = defense_rate(defense_state, h), defense_rate(defense_state, a)
            hp, ap = defense_rate(defense_state, h, "points"), defense_rate(defense_state, a, "points")
            epa_pick = h if he < ae else a if he > ae else None if he is not None and ae is not None else None
            # Avoid comparisons involving missing data.
            if he is None or ae is None:
                epa_pick = None
            ppg_pick = (h if hp < ap else a if hp > ap else None) if hp is not None and ap is not None else None
            winner = "TIE" if g.home_score == g.away_score else h if g.home_score > g.away_score else a
            e = elo_picks.get(str(g.game_id))
            row = {
                "week": week, "game_id": str(g.game_id), "home": h, "away": a,
                "home_score": int(g.home_score), "away_score": int(g.away_score),
                "winner": winner, "qbr_pick": selected, "epa_pick": epa_pick,
                "ppg_pick": ppg_pick, "elo_pick": e,
                "qbr_home": round(hq, 4) if hq is not None else None,
                "qbr_away": round(aq, 4) if aq is not None else None,
                "epa_home": round(he, 6) if he is not None else None,
                "epa_away": round(ae, 6) if ae is not None else None,
                "ppg_home": round(hp, 4) if hp is not None else None,
                "ppg_away": round(ap, 4) if ap is not None else None,
                "qbr_gap": round(abs(hq-aq), 4) if hq is not None and aq is not None else None,
                "valid_qbr": bool(selected and winner != "TIE"),
                "epa_available": bool(epa_pick),
                "qbr_correct": selected == winner if selected and winner != "TIE" else None,
                "epa_correct": epa_pick == winner if epa_pick and winner != "TIE" else None,
                "elo_correct": e == winner if e and winner != "TIE" else None,
                "both_agree": bool(selected and epa_pick and selected == epa_pick),
                "old_ppg_agree": bool(selected and ppg_pick and selected == ppg_pick),
            }
            rows.append(row)
        matched_2026 += add_week_to_state(slate, boxes, p26)

    if len(rows) != 92:
        raise RuntimeError(f"Completed-game cohort unexpectedly changed: {len(rows)}")
    eligible = [r for r in rows if r["valid_qbr"]]
    if len(eligible) != 77:
        raise RuntimeError(f"Original QBR 77-game sample not reproduced: {len(eligible)}")

    epa_valid = [r for r in eligible if r["epa_available"]]
    agree = [r for r in epa_valid if r["both_agree"]]
    disagree = [r for r in epa_valid if not r["both_agree"]]
    old = [r for r in eligible if r["old_ppg_agree"]]
    def compare_elo(sub):
        return measure(sub, "elo_correct")
    def group_info(sub):
        return {
            "qbr": measure(sub, "qbr_correct"),
            "epa": measure(sub, "epa_correct"),
            "elo": compare_elo(sub),
        }
    summary = {
        "definition": "Prior-week overall defensive EPA allowed per opponent offensive play; team weekly box aggregates (passing_epa+rushing_epa)/(attempts+carries). Lower is better. 2025 baseline for week 1; 2026 prior weeks for weeks 2-6.",
        "qbr_definition": "Same retrospective most-used current-game QB and prior-week plays-weighted ESPN Total QBR proxy as prior 77-game test; not independently confirmed starting QB",
        "coverage": {"completed_games": len(rows), "qbr_eligible": len(eligible),
                     "qbr_and_epa_eligible": len(epa_valid),
                     "epa_missing_among_qbr": len(eligible)-len(epa_valid),
                     "2025_games_with_paired_boxes": prev_year_games,
                     "2026_games_with_paired_boxes": matched_2026},
        "qbr_all_original": measure(eligible, "qbr_correct"),
        "qbr_on_same_epa_available_games": measure(epa_valid, "qbr_correct"),
        "qbr_and_better_defensive_epa_agree": group_info(agree),
        "qbr_epa_disagree": group_info(disagree),
        "defensive_epa_all_on_same_qbr_cohort": measure(epa_valid, "epa_correct"),
        "old_scoring_defense_agree": {"qbr":measure(old, "qbr_correct"),"elo":compare_elo(old)},
        "week": [],
        "qbr_gap": [],
    }
    for week in range(1, 7):
        s=[r for r in eligible if r["week"]==week]
        a=[r for r in s if r["both_agree"] and r["epa_available"]]
        d=[r for r in s if r["epa_available"] and not r["both_agree"]]
        summary["week"].append({"week": week,"qbr_eligible":len(s),
                                 "epa_eligible":sum(r["epa_available"] for r in s),
                                 "agree":group_info(a), "disagree":group_info(d)})
    for lo,hi in ((0,5),(5,10),(10,20),(20,None)):
        subset=[r for r in agree if r["qbr_gap"] >= lo and (hi is None or r["qbr_gap"] < hi)]
        summary["qbr_gap"].append({"bucket": f"{lo} to {hi or 'plus'}", **group_info(subset)})
    payload={"summary":summary,"games":rows}
    Path("qbr_defensive_epa_2026.json").write_text(json.dumps(payload,indent=2))
    pd.DataFrame(rows).to_csv("qbr_defensive_epa_2026.csv",index=False)
    print("DEFENSIVE_EPA_RESULT_BEGIN",flush=True)
    print(json.dumps(summary,indent=2),flush=True)
    print("DEFENSIVE_EPA_RESULT_END",flush=True)

if __name__ == "__main__":
    main()
