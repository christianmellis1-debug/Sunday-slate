# NFL opening-to-closing spread movement backtest

2024: ESPN BET. 2025–2026 (completed weeks 1–6): DraftKings.
Only regular-season final games with complete and internally consistent same-book opening/closing spreads are included.
The movement side is whichever team saw its signed spread decrease, making the market more favorable to it.
SU means outright wins; ATS is separately calculated against opening and closing spreads; pushes are excluded from percentages.
Source: ESPN scoreboards and ESPN Core odds. This is independent of Sunday Slate's Elo model.

## by season
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 2024 | 204 | 109-95-0 (53.4%) | 102-93-9 (52.3%) | 95-109-0 (46.6%) |

## by magnitude 2025 2026 draftkings
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|

## by magnitude all books
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 0.5 point | 41 | 24-17-0 (58.5%) | 18-19-4 (48.6%) | 18-23-0 (43.9%) |
| 1 point | 72 | 36-36-0 (50.0%) | 36-36-0 (50.0%) | 33-39-0 (45.8%) |
| 1.5–2.5 points | 60 | 30-30-0 (50.0%) | 29-26-5 (52.7%) | 27-33-0 (45.0%) |
| 3+ points | 31 | 19-12-0 (61.3%) | 19-12-0 (61.3%) | 17-14-0 (54.8%) |

## by open role
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| Favorite | 104 | 74-30-0 (71.2%) | 54-45-5 (54.5%) | 50-54-0 (48.1%) |
| Pick'em | 1 | 1-0-0 (100.0%) | 1-0-0 (100.0%) | 1-0-0 (100.0%) |
| Underdog | 99 | 34-65-0 (34.3%) | 47-48-4 (49.5%) | 44-55-0 (44.4%) |

## Audit and limitations
Same-book prices only. Books and seasons must not be mistaken for equivalent populations.
ESPN's stored open/close fields have no independent observation timestamps; opening prices differ across books.
Opening ATS cover rates can be mechanically better than closing ATS when the market moves toward a team.
The test does not validate real-time odds availability, bet execution, or profitability.
Uncovered games and provider/API failures are excluded; consult summary JSON audit.
