# Sunday Slate — Proposed Tier Validation (research-only)

**As-of:** October 13, 2026. **Source:** [successful tier-research workflow](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/38427277209), generated from NFLverse preweek team results/EPA.  
**Immutable candidate:** [frozen 2019–2022 Elo + scoring form + adjusted EPA coefficients](frozen_form_epa_v1.json).  
**First pregame snapshot:** [2026 Week 6](snapshots/2026_week_06.json), archived at **2026-10-13 16:03:27 UTC**, before the games were played.

## Rules — mutually exclusive, in priority order

| Tier | Research-only rule |
| --- | --- |
| **Tier 1 · Elite Rating** | Unmodified Elo confidence **75% or greater** |
| **Tier 2 · Double Confirmation** | After excluding Tier 1: Elo confidence **60%+**, projected winning margin by adjusted PPG **7+ points**, Elo and PPG select same side, both teams **3+ prior games** |
| **Tier 3 · Solid Consensus** | After excluding Tiers 1–2: Elo confidence **60%+**, Elo and adjusted PPG select same side, both teams **3+ prior games** |
| **Tier 4 · Uncertain** | All other games. **Not a betting recommendation** |

These are **straight-up** classifications, independent of spreads and sportsbook odds. Historical 2023–2025 data has been repeatedly inspected, therefore these are not pristine out-of-sample validations.

## Historical results, same exclusive tiers

| Group | 2019–2022 development | 2023–2025 retrospective | 2026 preliminary |
| --- | ---: | ---: | ---: |
| Tier 1 | 88–28 (75.9%), 116 games | **62–14 (81.6%), 76 games** | **7–1 (87.5%), 8 games** |
| Tier 2 | 49–16 (75.4%), 65 games | **47–16 (74.6%), 63 games** | 1–1 (50.0%), 2 games |
| Tier 3 | 200–81 (71.2%), 281 games | 139–61 (69.5%), 200 games | 4–1 (80.0%), 5 games |
| Tier 4 | 345–243 (58.7%), 588 games | 270–206 (56.7%), 476 games | 40–23 (63.5%), 63 games |
| **Tier 1–3 total** | **337–125 (72.9%), 462 games** | **248–91 (73.2%), 339 games** | **12–3 (80.0%), 15 games** |

Tier 1 has a comparatively stable above-75% record across 2023–2025: **14–4 (77.8%)**, **21–3 (87.5%)**, **27–7 (79.4%)**. Tier 2 is smaller: **20–7**, **11–5**, **16–4**. Tier 3 is unstable: **40–22 (64.5%)**, **60–15 (80.0%)**, **39–24 (61.9%)**.

2023–2025 Tier 1–3 covers **339/815 = 41.6%** of the regular season; the remaining 58.4% would be Tier 4. **High selective accuracy does not imply the full model exceeds 66%.**

## Does the frozen challenger add value within tiers?

| Cohort, 2023–2025 | Elo result | Frozen challenger result | Net additional winners |
| --- | ---: | ---: | ---: |
| Tier 1–3 combined | 248–91 | 247–92 | **−1** |
| Tier 4 | 270–206 | 298–178 | **+28** |
| All games | 518–297 | 545–270 | **+27** |

Nearly all historical improvement comes **outside** the strongest Elo confidence/PPG consensus tiers. This is where an experimental model might identify Elo mistakes, but preliminary 2026 results reverse:

- Tier 4 2026 Elo **40–23 (63.5%)**, challenger **37–26 (58.7%)**.
- Elo and challenger disagreed on **85 games** in 2023–2025: challenger **56–29 (65.9%)**, Elo **29–56 (34.1%)**.
- They disagreed on only **7 games** in early 2026: challenger **2–5 (28.6%)**, Elo **5–2 (71.4%)**.

This instability **rules out** an automatic challenger override or newly recommended high-confidence betting tier for now.

## Frozen 2026 Week 6 forecasts

All **14 upcoming games** were frozen in the [Week 6 archive](snapshots/2026_week_06.json), **before kickoff**, with a source digest. **Elo and challenger agreed on all 14 predicted winners**. There are no past results in the snapshot. **Do not update/overwrite snapshots**, even if live input data changes.

- **Tier 1 (3):** Arizona at Los Angeles Rams (**LA**), NY Jets at New England (**NE**), Washington at San Francisco (**SF**).
- **Tier 2 (1):** Los Angeles Chargers at Kansas City (**KC**).
- **Tier 3 (4):** Baltimore at Cleveland (**BAL**), Dallas at Green Bay (**GB**), Houston at Jacksonville (**JAX**), Tennessee at Indianapolis (**IND**).
- **Tier 4 (6):** Buffalo at Las Vegas (**BUF**), Carolina at Philadelphia (**PHI**), Chicago at Atlanta (**CHI**), New Orleans at NY Giants (**NYG**), Pittsburgh at Tampa Bay (**PIT**), Seattle at Denver (**DEN**).

Every Tuesday morning the [scheduled GitHub workflow](../.github/workflows/frozen-forecast-tiers.yml) attempts to append a fresh, fully unplayed NFL-week snapshot and grades only old frozen predictions. Existing snapshots are never overwritten. Scheduling is best-effort; always verify the run actually completed and was before first kickoff.

## Recommendation

1. Maintain deployed Elo and existing football analytics.
2. Label **Tier 1** as the clearest straight-up research shortlist; investigate the smaller Tier 2 further.
3. **Hold off promoting Tier 3** as high-conviction. Treat Tier 4 as low confidence/risk, potentially a separate improvement target.
4. Re-assess as new 2026 results arrive using **the archived predictions**, not restated past picks.
5. No DraftKings feed is connected. **No ATS, odds-based tier, or profitability claim** is supported here. User has explicitly held off on the API.

Research code: [tier backtest](tiers_validation.py) · [frozen weekly forecaster](frozen_weekly.py).
