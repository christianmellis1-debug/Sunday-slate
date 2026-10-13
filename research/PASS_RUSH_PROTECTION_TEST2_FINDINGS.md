# Sunday Slate — Test 2: Pass Rush vs. Offensive Line Protection

Research date: 2026-10-13. **Production NFL-ELO-1.0 unchanged.**

## Experimental definition and provenance

- NFLverse play-by-play for 2019–2026, 3,900 offense-by-game records and 1,943 graded regular-season games through 2026 Week 5.
- Pressure proxy: `qb_hit OR sack` when `qb_dropback == 1`. This is NOT a complete charted pressure rate, offensive-line-only pass-blocking grade, or Next Gen Stats time-to-pressure.
- One input snapshot per week generated **before** updating any team's weekly PBP rates. Actual current-game scores and dropbacks never inform their own predictions.
- Raw pressure advantage compares team's prior defensive hits/sacks caused against its opponent's prior hits/sacks allowed; adjust by prior opponent tendencies in a separate feature; a recent four-game feature and sacks-only feature are independent variants.
- Fits logistic models on **2019–2022 (1,050 decisive games)** only. Compares to unchanged Elo and an Elo-only recalibration using the same development seasons. **2023–2025 (815 games)** was examined across six candidates, so selecting a winner from these seasons is retrospective multiple-testing and does not create a fresh untouched holdout.
- 2026 Week 1–5 (78 games) separately evaluated without refitting or using future results.
- ATS is **nflverse historical closing/reference spread** using `home_score-away_score - spread_line` (spread_line positive means home favored); not an audited FanDuel/DraftKings pregame price. Pushes excluded from cover percentages. ATS record is not demonstrated ROI.

## Full-slate results, 2023–2025 holdout (815 games)

| Variant | Straight-up | Accuracy | Brier | Reference ATS (19 pushes) |
|---|---:|---:|---:|---:|
| Production Elo | 518–297 | 63.56% | .22309 | 394–402 |
| Elo recalibration | 526–289 | 64.54% | .22320 | 400–396 |
| Elo + raw pressure | 537–278 | 65.89% | .22224 | 411–385 |
| Elo + opponent-adjusted pressure | 534–281 | 65.52% | .22250 | 408–388 |
| Elo + sack-only | 529–286 | 64.91% | .22322 | 406–390 |
| Elo + last-four pressure | 535–280 | 65.64% | .22340 | 410–386 |
| Elo + raw plus opponent-adjusted | **540–275** | **66.26%** | **.22211** | **413–383** |

The combined model changed 46 matches relative to Elo, correcting 34 incorrect winners and introducing 12 new mistakes (net +22). The Brier gain is modest: .00098. A flat bet at standard -110 requires ~52.38% cover rate excluding pushes; combined ATS cover = 51.88%; no verified price availability/ROI.

## Year-by-year

| Year | Production Elo | Combined pressure | Difference |
|---|---:|---:|---:|
| 2023 | 165–107 | 172–100 | +7 |
| 2024 | 179–93 | 189–83 | +10 |
| 2025 | 174–97 | 179–92 | +5 |
| 2026 through W5 (preliminary) | 52–26 | 48–30 | -4 |

2026: all four changes were incorrect reversals of correct Elo picks:
- 2026_02_JAX_DEN (two teams with one prior week);
- 2026_03_CAR_CLE (two prior games);
- 2026_04_DEN_SF (three prior games);
- 2026_04_IND_WAS (three prior games).
No erroneous Elo choices were corrected in 2026. This requires further validation before changing the official model.

## Dominant-pass-rush selective signal

Rule: each team needs >=3 earlier games with >=100 prior team dropbacks, compare all eligible teams in that week's rankings, select a sole side if its defense has upper-quartile QB hits/sacks inflicted and its opponent's offense has upper-quartile QB hits/sacks allowed.

2023–2025: **71** qualifying matches, straight-up **38–33 (53.52%)**, ATS **34–37 (47.89%)**, no pushes; underdogs straight-up **5–11** and ATS **6–10**. Does **not** merit its own tier.

2026 W1–5: 1 signal (1–0 both SU and reference ATS), far too few games to evaluate.

## Exploratory minimum-prior-games gates

When a team has too few previous games, preserve Elo rather than activating combined pressure. This is **post-hoc sensitivity** chosen after viewing the 2026 errors; must not be called independent verification.

| Gate | 2023–2025 SU | 2026 SU |
|---|---:|---:|
| No gate | 540–275 (66.26%) | 48–30 (61.54%) |
| >=3 prior games | 537–278 (65.89%) | 50–28 (64.10%) |
| >=4 prior games | 536–279 (65.77%) | 52–26 (66.67%) |
| >=5 prior games | 533–282 (65.40%) | 52–26 (66.67%) |
| Original Elo | 518–297 (63.56%) | 52–26 (66.67%) |

The four-game gate eliminates added errors without improving current 2026; no new model is ready for promotion.

## Reproducibility and validation

- Runner: `python -m research.pass_rush_protection_test2 --output pass_rush_protection_test2_results.json`
- Workflow: `.github/workflows/pass-rush-protection-test2.yml`
- Unit tests: `python -m pytest -q tests/test_pass_rush_protection_test2.py` (3 passed).
- Per-year QB-hit observation coverage was 100% for all dropback records in the studied PBP datasets; all 1,950 completed regular-season games in the study years matched both teams' PBP aggregates, including tied games; no missing game-to-PBP joins.
- The latest workflow artifact retains the full JSON, including Brier/log loss, 2026 flipped-game audit, threshold sensitivity and development results.
- Code and documents are on `research/pass-rush-protection-test2-20261013`, not deployed to the main production model.

**Decision:** Keep Sunday Slate's official Elo model and betting tiers unchanged. Continue prospective 2026 validation of the fixed, four-previous-games pressure challenger. If it shows sustained improvement, consider adding a clearly labeled QB pressure matchup indicator and then a separately validated full-slate model update. No positive ATS profitability claim is supported.
