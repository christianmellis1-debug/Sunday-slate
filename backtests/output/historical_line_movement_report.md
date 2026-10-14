# NFL opening-to-closing spread movement backtest

2024: ESPN BET. 2025: DraftKings if published, otherwise ESPN BET (same-book comparisons only). 2026: DraftKings (completed games through October 14).
Only regular-season final games with complete and internally consistent same-book opening/closing spreads are included.
The movement side is whichever team saw its signed spread decrease, making the market more favorable to it.
SU means outright wins; ATS is separately calculated against opening and closing spreads; pushes are excluded from percentages.
Source: ESPN scoreboards and ESPN Core odds. This is independent of Sunday Slate's Elo model.

## by season provider
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 2024 | ESPN BET | 204 | 109-95-0 (53.4%) | 102-93-9 (52.3%) | 95-109-0 (46.6%) |
| 2025 | DraftKings | 67 | 43-24-0 (64.2%) | 38-27-2 (58.5%) | 34-33-0 (50.7%) |
| 2025 | ESPN BET | 120 | 60-60-0 (50.0%) | 63-56-1 (52.9%) | 56-64-0 (46.7%) |
| 2026 | DraftKings | 67 | 35-31-1 (53.0%) | 35-32-0 (52.2%) | 28-35-4 (44.4%) |

## by season
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 2024 | 204 | 109-95-0 (53.4%) | 102-93-9 (52.3%) | 95-109-0 (46.6%) |
| 2025 | 187 | 103-84-0 (55.1%) | 101-83-3 (54.9%) | 90-97-0 (48.1%) |
| 2026 | 67 | 35-31-1 (53.0%) | 35-32-0 (52.2%) | 28-35-4 (44.4%) |

## by magnitude 2025 2026 draftkings
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 0.5 point | 31 | 12-19-0 (38.7%) | 11-19-1 (36.7%) | 9-20-2 (31.0%) |
| 1 point | 24 | 13-10-1 (56.5%) | 12-12-0 (50.0%) | 12-12-0 (50.0%) |
| 1.5–2.5 points | 30 | 22-8-0 (73.3%) | 19-10-1 (65.5%) | 16-13-1 (55.2%) |
| 3+ points | 49 | 31-18-0 (63.3%) | 31-18-0 (63.3%) | 25-23-1 (52.1%) |

## by magnitude all books
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| 0.5 point | 76 | 37-39-0 (48.7%) | 30-40-6 (42.9%) | 28-46-2 (37.8%) |
| 1 point | 165 | 85-79-1 (51.8%) | 83-82-0 (50.3%) | 78-87-0 (47.3%) |
| 1.5–2.5 points | 110 | 62-48-0 (56.4%) | 62-42-6 (59.6%) | 56-53-1 (51.4%) |
| 3+ points | 107 | 63-44-0 (58.9%) | 63-44-0 (58.9%) | 51-55-1 (48.1%) |

## by open role
| Group | Games | SU W-L-P (%) | ATS open W-L-P (%) | ATS close W-L-P (%) |
|---|---:|---|---|---|
| Favorite | 249 | 169-79-1 (68.1%) | 128-115-6 (52.7%) | 114-133-2 (46.2%) |
| Pick'em | 1 | 1-0-0 (100.0%) | 1-0-0 (100.0%) | 1-0-0 (100.0%) |
| Underdog | 208 | 77-131-0 (37.0%) | 109-93-6 (54.0%) | 98-108-2 (47.6%) |

## Audit and limitations
Same-book prices only. Books and seasons must not be mistaken for equivalent populations.
ESPN's stored open/close fields have no independent observation timestamps; opening prices differ across books.
Opening ATS cover rates can be mechanically better than closing ATS when the market moves toward a team.
The test does not validate real-time odds availability, bet execution, or profitability.
Uncovered games and provider/API failures are excluded; consult summary JSON audit.
