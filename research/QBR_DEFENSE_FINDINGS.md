# Research Scenario 01 — QB Total QBR versus scoring defense

**Date tested:** October 9, 2026  
**Seasons:** 2023, 2024, 2025 NFL regular season (2026 YTD separately).  
**Primary question:** How often did the team with a higher pregame QB QBR win, versus the team with a better pregame scoring defense?  
**Prediction model:** No changes to NFL-ELO-1.0; scenario is research-only.

## Locked definitions

- **Quarterback Total QBR:** The latest four *prior* weeks of ESPN weekly Total QBR; estimate a play-count-weighted average for the team's most-used quarterback during those weeks. Minimum 30 recorded QB plays. The QB may not be the future starter. This weighted mean is an **approximation of rolling Total QBR**, not an independently published ESPN trailing-four-game metric.
- **Defense:** Fewer opponent points allowed per prior completed regular-season game, in the same season, measured before the target week.
- Missing QB metrics, defenses with no earlier games, exact ties, and tied game outcomes are excluded for each respective metric; **do not** include the matchup's own game or later games in its predictors.
- Comparisons in the first two rows below use different eligible game sets; subsequent same-game comparisons correct for that.
- Source: [nflverse NFL schedule](https://github.com/nflverse/nfldata/blob/master/data/games.csv) and [nflverse ESPN Total QBR release](https://github.com/nflverse/nflverse-data/releases/tag/espn_data). These are retrospective data releases; historical revisions are possible.

## 2023–2025 observed results

| Pregame factor | W–L | Win rate | Eligible games |
| --- | --- | ---: | ---: |
| Higher recent weighted ESPN Total QBR | 407–326 | **55.53%** | 733 |
| Lower points allowed per game | 435–322 | **57.46%** | 757 |
| Both factors point to same team | 248–150 | **62.31%** | 398 |
| Frozen Sunday Slate Elo on those **same 398 games** | 271–127 | **68.09%** | 398 |
| All three factors agree (QBR + defense + Elo) | 222–101 | **68.73%** | 323 |
| QBR + defense agree **against** Elo | 26–49 | **34.67%** | 75 |
| When factors disagree: follow QB metric | 155–171 | **47.55%** | 326 |
| When factors disagree: follow defense metric | 171–155 | **52.45%** | 326 |

### Season splits

| Season | Higher QB QBR | Better scoring defense | Two factors agree |
|---|---:|---:|---:|
| 2023 | 135–110 (55.10%) | 134–117 (53.39%) | 74–55 (57.36%) |
| 2024 | 134–106 (55.83%) | 139–114 (54.94%) | 78–50 (60.94%) |
| 2025 | 138–110 (55.65%) | 162–91 (64.03%) | 96–45 (68.09%) |

The scoring-defense signal was notably stronger in 2025 than 2023–2024, suggesting unstable year-to-year usefulness.

### Robustness probes — descriptive, not optimized rules

- If both teams have **at least three prior completed games**, the lower PPG-allowed team was **394–273, 59.07%** on its eligible games. When it also agreed with the higher recent QB QBR: **224–128, 63.64%**.
- If both QB samples meet **100 plays over the prior four weeks**, the higher-QBR team was **257–200, 56.24%**. Both factors together agreed on **164–91, 64.31%**.

These thresholds were inspected after the initial scenario; they are exploratory and must not be treated as a validated betting edge.

### Main conclusion

Higher QBR and lower PPG allowed are moderately predictive in isolation, and combined 62.31% on shared-direction games. **Neither replaces the existing Elo baseline**: on exactly the same 398 agreement games, Elo picked 271 winners (68.09%). When both indicators *disagreed* with Elo, the QBR/defense choice won only 26 of 75 (34.67%); when all three agreed, the shared pick won 222 of 323 (68.73%). Better defensive efficiency, quarterback matchup features, opponent strength, and interaction with Elo warrant controlled follow-up, not immediate model or betting-tier changes.

### Limitations

- Scoring defense = points allowed per game, not an opponent-adjusted EPA or yards-allowed ranking.
- No home/away, odds, spreads, public injuries, or QB starter confirmation used to define the two scenario picks.
- The QBR four-week average is an approximation; ESPN's official composite QBR is not exactly reducible to averaging reported weekly Total QBR.
- Historical data availability is not a guarantee these exact retrospective releases existed at the beginning of each original week.
- Straight-up wins only. **No ATS or betting ROI conclusions** without historical executable pre-kickoff sportsbook quotes.
- This analysis tests simple predictors, not whether either improves the already-built model through retraining.

## Reproduce

```bash
python -m research.test_qbr_defense --output qbr_defense_results.json
```

GitHub [research job](https://github.com/christianmellis1-debug/Sunday-slate/actions/workflows/qbr-defense-research.yml) runs with current data and makes the full JSON results available as a workflow artifact. For pinned reproduction supply `--games games.csv --qbr qbr_week_level.csv`.
