# US100 M1 cash-open fair-price reversion — exploratory protocol

## Question and status

Test one mechanical, source-faithful translation of the requested video idea:
an M1 cash-open impulse away from a pre-open fair-price anchor, consolidation
with lower tick volume, then a market entry on the first structure break back
toward the anchor. The frozen terminal history spans only about fifteen weeks;
this is an exploratory test, not a gate-grade FTMO pass-rate estimate and not
an authorization to change or deploy an EA.

## Fixed data and timestamp convention

Input is only the immutable US100 M1 freeze verified by
`python backtest/freeze_video_m1_us100.py --verify`, with manifest
`backtest/ftmo_m1_us100_video_20260713.manifest.sha256`. Epochs are UTC. The
cash-open schedule in this data window is 13:30 UTC (09:30 New York daylight
time). A session is skipped unless every M1 bar named below is present.

## One tested cell: `OPEN_M1_FAIR_3R`

For each weekday session:

1. Fair-price anchor is the 13:29 UTC M1 close. Pre-open scale is the median
   high-low range of bars 13:15 through 13:29 inclusive; skip zero/non-finite
   scale.
2. The 13:30 impulse must close away from the anchor by at least one pre-open
   scale, and have a body in the same direction. An up impulse proposes a
   short reversion; a down impulse proposes a long reversion.
3. Consolidation is exactly 13:31–13:34. Every bar must remain on the impulse
   side of the anchor, its total high-low span must not exceed 1.5 pre-open
   scales, and its mean tick volume must be no greater than the 13:30 bar's
   tick volume.
4. Search 13:35–14:15 inclusive for the first M1 close that breaks back toward
   fair price: after an up impulse, close below the lowest consolidation low;
   after a down impulse, close above the highest consolidation high. Enter at
   that signal close as a market order. Only one entry per session is possible.
5. For a short, stop is consolidation high plus 0.10 pre-open scale, evaluated
   as an ask; for a long, stop is consolidation low minus 0.10 pre-open scale,
   evaluated as a bid. The target is exactly 3R toward the fair-price anchor.
   Skip the signal unless that 3R target lies at or before the anchor.
6. Hold from the following M1 bar until first stop/target or 15:55 UTC. A long
   market entry is signal close plus that bar's observed spread × point; a
   short is the signal close bid. Long exits use bid high/low; short exits use
   bid low and ask high (bar high plus that bar's observed spread × point).
   If stop and target occur in one M1 bar, score stop first. A session timeout
   exits at the 15:55 close on the executable side. No partials, breakeven,
   trailing stop, re-entry, sizing, or additional filter is permitted.

## Reporting and no-tuning rule

Report every complete session, candidate, skipped candidate reason, and trade.
Report count, win rate, mean R, median R, and the chronological split using
the first 60% and final 40% of complete session dates. The final-40% result is
descriptive only: all constants above were selected before any outcome is
computed, and no retry, parameter adjustment, symbol extension, or deployment
follows a failed cell. Spread is modeled from each observed bar; cash commission
and slippage beyond bar-spread are not available in the frozen M1 data and must
not be inferred as zero in any live claim.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `6413ac7c63ea2f629951ba43c7edb1419bf913a2ac4981b59ea6c219f037b872`
