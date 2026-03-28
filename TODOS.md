# TODOS

## Adaptive Engagement Threshold
**What:** Replace the fixed score-40 auto-capture threshold with one that learns from user behavior (saves-to-zettel rate, manual captures, reading patterns).
**Why:** The fixed threshold of 40 is calibrated by intuition. Fast skimmers may never hit 40; deep readers always exceed it. An adaptive threshold would reduce false positives (noisy captures of content the user didn't care about) and false negatives (missed articles the user engaged with but didn't trigger the threshold).
**How to start:** After v1 ships, collect 2 weeks of engagement score data. Analyze the distribution of scores for pages the user manually saved vs. pages that were auto-captured but never revisited. Use the crossover point as the new threshold.
**Depends on:** Smart Reader v1 being live and generating engagement data in `reading_sessions` table.
**Added:** 2026-03-27 via /plan-eng-review
