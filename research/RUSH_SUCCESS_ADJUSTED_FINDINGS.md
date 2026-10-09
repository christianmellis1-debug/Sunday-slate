# Scenario 04 — Rushing success and opponent-adjusted rushing EPA

**Date tested:** 2026-10-09.  
**Execution:** [successful research GitHub run](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/37990528394) (JSON and reduced neutral-play summaries available as artifacts).  
**Source code:** [rush_success_adjusted.py](rush_success_adjusted.py).  
**Regression tests:** [test_rush_success_adjusted.py](../tests/test_rush_success_adjusted.py).  
**Impact on deployed predictor:** **None**. NFL-ELO-1.0 remains unchanged.

## Frozen research definition

1. NFLverse play-by-play (2019–2026), using *designed rushes* only: `play_type="run"`, `rush_attempt=1`, no quarterback scramble or kneel. Retain quarters 1–3 only when the **preplay** score difference is within 14 points. Exclude missing down, yards-to-go, yards gained, EPA, offense or defense. This is an explicit *neutral-ish* game-script filter, not a guarantee every play was neutral.
2. Conventional **success rate** is yards gained / yards to first down: **40%** or more on first down, **60%** or more on second, **100%** or more on third or fourth. This differs from NFLverse `success` (positive EPA), so the analysis computes the 40/60/100 rate directly.
3. **Opponent-adjusted rushing EPA** uses the sum of filtered-play EPA divided by filtered-play attempts for each previous game/offense. Fit a weighted two-way regression to **previous games only**: rushing EPA/attempt = intercept + offensive team effect + defensive team effect. Use rushing attempt counts as regression weights and an explicit ridge penalty equivalent to **150 rushing attempts** on each team effect. **Lower defensive allowed EPA effect is better defense; lower offensive EPA effect is weaker rushing offense.**
4. Rebuild all statistics at the *beginning* of each target week, before updating with any target-week games. Teams need at least **3 completed previous regular-season games**. Qualify if an elite defense faces a weak offense: defensive and opposing offensive metrics both in their lowest **25%** of eligible teams; one-sided signals only, excluding ties/ambiguous matches. Compare raw success rate, opponent-adjusted EPA, and cases where both select the same team.
5. Top/bottom **20%, 25%, 33⅓%, 40%** are sensitivity checks; **25% is the primary definition**, declared before running results.
6. **2019–2022:** earlier discovery data. **2023–2025:** later chronological evaluation. **2026** is incomplete and diagnostic only.
7. Grade straight-up against frozen Sunday Slate NFL-ELO-1.0 on *the identical games*. Grade against the historical NFLverse reference closing spread, excluding pushes/missing lines. These are not verified pre-kickoff bets, ROI, or investment recommendations.

## Primary 25% research result

### Later 2023–2025 evaluation

| Pregame rule | SU W–L (games) | Elo on identical games | Historical ATS (graded spreads) | Contradict Elo |
| --- | --- | --- | --- | --- |
| Rushing success | 45–21 (66), **68.18%** | 46–20, **69.70%** | 38–28 (66), **57.58%** | 8–9 on 17 conflicts |
| **Opponent-adjusted rushing EPA** | **59–16 (75), 78.67%** | **55–20, 73.33%** | **43–31 (74), 58.11%** | **7–3 on 10 conflicts** |
| Both metrics agree | 18–4 (22), **81.82%** | 16–6, **72.73%** | 12–10 (22), **54.55%** | 2–0 on 2 conflicts |

The apparent **four extra correct predictions** from adjusted EPA are from **only ten games where it disagreed with Elo**. That is insufficient to establish statistical improvement, and the research was motivated by observations in previously inspected data.

### Discovery-period comparison (2019–2022)

| Pregame rule | Signal SU W–L | Elo identical games | Historical ATS |
| --- | --- | --- | --- |
| Rushing success | 66–36 (102), 64.71% | 66–36, 64.71% | 52–45 (97), 53.61% |
| **Opponent-adjusted rushing EPA** | **62–34 (96), 64.58%** | 61–35, 63.54% | **51–43 (94), 54.26%** |
| Both metrics agree | 22–13 (35), 62.86% | 21–14, 60.00% | 17–17 (34), 50.00% |

The adjusted EPA result exceeded Elo by just **one extra correct game** in discovery. That is directional consistency but *not* a validated improvement.

### By year, adjusted EPA 25%

| Season | Adjusted EPA SU | Elo SU, same games | Historical ATS |
| --- | --- | --- | --- |
| 2019 | 13–7 | 12–8 | 8–11 |
| 2020 | 16–7 | 15–8 | 13–10 |
| 2021 | 17–9 | 17–9 | 15–11 |
| 2022 | 16–11 | 17–10 | 15–11 |
| **2023** | **16–6** | **13–9** | **12–10** |
| **2024** | **24–4** | **23–5** | **20–7** (one ungraded) |
| **2025** | **19–6** | **19–6** | **11–14** |
| 2026 YTD (tiny sample) | 1–2 | 3–0 | 0–2 (one ungraded) |

**ATS is inconsistent by year:** the high 2024 cover rate dominates the encouraging overall percentage; the 2025 ATS screen lost more than it won. The current 2026 sample is only three games.

### Threshold sensitivity on the later 2023–2025 period

| Filter | Selected games | SU signal | Elo SU, same games | ATS (reference lines) |
| --- | --- | --- | --- | --- |
| Adjusted EPA 20% | 59 | 45–14 (76.27%) | 45–14 (76.27%) | 33–26 (55.93%) |
| **Adjusted EPA 25%** | **75** | **59–16 (78.67%)** | **55–20 (73.33%)** | **43–31 (58.11%)**, one excluded |
| Adjusted EPA 33⅓% | 134 | 100–34 (74.63%) | 102–32 (76.12%) | 81–51 (61.36%) |
| Adjusted EPA 40% | 180 | 127–53 (70.56%) | 127–53 (70.56%) | 105–72 (59.32%) |
| Both indicators 20% | 14 | 11–3 (78.57%) | 11–3 | 6–8 (42.86%) |
| Both indicators 25% | 22 | 18–4 (81.82%) | 16–6 | 12–10 (54.55%) |
| Both indicators 33⅓% | 42 | 37–5 (88.10%) | 36–6 | 27–15 (64.29%) |
| Both indicators 40% | 77 | 57–20 (74.03%) | 59–18 | 42–33 (56.00%), two excluded |

The 33⅓%-both agreement has an attractive 37–5 historical win record but **is a post-hoc sensitivity result**, with only 42 games, multiple comparisons, no prospective validation, and an Elo model that itself went 36–6 on the very same set. It is *not* an official tier or forecast accuracy promise.

## Why the adjusted result is worth studying but not deploying yet

- Unlike raw EPA from the previous study, the current experiment removes some runaway-game situations and shrinks EPA effects after controlling for the defenses/offenses faced. That is a more plausible football feature than season-to-date yards per carry alone.
- The main adjusted EPA selection **did** outperform Elo on exactly the same later-period games (59 vs 55 correct), but only ten forecasts actually disagreed. On those ten, the signal was 7–3, Elo 3–7. A binomial/McNemar-style 7–3 split is *not* strong evidence at conventional significance thresholds (two-sided p≈0.344).
- On the early discovery years, those Elo disagreements were 15–14 for the adjusted signal: effectively even.
- **This is not a time-stamped as-of historical dataset**: NFLverse may revise EPA values and reference spreads in past releases. All feature engineering is chronologically leak-controlled on those retrospective versions.
- The ridge correction accounts for prior opponent run strength but does not address personnel availability, down-distance imbalance within aggregates, defensive front, or all aspects of game script.
- A 58.11% closing reference ATS cover rate without verified bookmaker odds and price does not establish positive prospective expected value or executable profits; betting vig matters.
- The 2026 season-to-date adjusted EPA sample was **1–2**, far too small to resolve anything.

## Decision

**Preserve Elo** and retain the neutral-script opponent-adjusted EPA signal as a strong research candidate. Do not present it as official value picks or new betting tier. Next: freeze its exact weekly predictions prospectively, collect actual pre-kickoff book prices, and benchmark Elo + adjusted EPA using a calibrated probability model and rolling time splits. Only promote it if it beats Elo on Brier, log loss, *and* relevant ATS/odds-grade outcomes on genuinely new games.

## Data coverage and rerun

The analysis processed **63,030** neutral-script rushing plays: 8,209 (2019); 8,303 (2020); 8,769 (2021); 9,195 (2022); 8,683 (2023); 8,890 (2024); 8,792 (2025); 2,189 (2026 through Oct 9). **3,872** game/offense summaries, **1,936** paired game-level rushing summaries. Elo historical matching covered **1,930** decisive games.

```bash
python -m research.rush_success_adjusted --output rush_success_adjusted_results.json
```

The GitHub workflow saves the full JSON and the pregame-compatible filtered per-game rushing summaries, so the results can be reproduced without re-downloading all play-by-play data:
```bash
python -m research.rush_success_adjusted --aggregates neutral_rushing_game_aggregates.csv --output rerun.json
```
