---
title: Team Talks & Shouts — Improvement Roadmap
slug: team-talks-shouts-roadmap
category: proposals
tags: [team-talks, shouts, roadmap]
source: derived from our manual pages (Playing a Match, Squad & Dynamics, Manager Profile, Tactics)
last_updated: 2025-09-24
---

# Team Talks & Shouts — Improvement Roadmap

Scope: ideas only (no implementation). These proposals are grounded in the current manual content and target higher quality, safer, and clearer recommendations for pre/half-time/full-time team talks and in‑play shouts.

## Goals

- Make recommendations context‑aware (venue, match importance, morale trend, unit performance, cards, fatigue).
- Provide safer defaults with guardrails and transparent “Why this” rationales.
- Reduce user effort with audience targeting (team, units, individuals) and cool‑down logic for shouts.
- Support extra-time and shootout phases explicitly.

## Team Talks

1) Context matrix for tone selection
- Inputs: venue (home/away/neutral), favourite/underdog, importance (league/cup/derby/final), morale trend (last 5), HT score delta and xThreat proxy, card state (reds/yellows), injuries.
- Output: ranked tones with weights (e.g., Calm 0.6, Encourage 0.3, Assertive 0.1) plus disallow list for risky options in given context.

2) Audience segmentation
- Targets: Whole Team (default), Units (DEF/MID/ATT), Bench, Individuals, Leaders cohort (from Hierarchy).
- Rule: start with a whole‑team message; add unit overrides when unit performance diverges (e.g., DEF < 6.5 average rating while ATT > 7.0 → sympathise with DEF, praise ATT).

3) Tone escalation ladder (per phase)
- Ladder per phase: Pre‑match (Calm → Encourage → Assertive), Half‑time (Calm/Encourage → Demand More/Disappointed → Hairdryer), Full‑time (Calm/Praise/Disappointed depending on expectation).
- Escalate only if previous talk underperformed (reflected by poor reaction or slumping ratings); decay ladder between matches.

4) Talk + Gesture synergy
- Maintain a compatibility map between tones and gestures by context (favourite, derby, losing/winning). Penalise clashes (e.g., Calm + Finger Wag).
- Return: best combo with a confidence score and “safer”/“bolder” alternatives.

5) Micro‑targeted nudges
- Per‑player suggestions using: match rating band, body‑language proxy (nervous/composed), promise pressure (Playing Time), card state, stamina.
- Examples: Praise high raters/youngsters; caution booked defenders; encourage low‑confidence attackers.

6) Extra‑time and shootout presets
- Dedicated presets for ET start, ET half, pre‑shootout (Composed vs Fire Up) and keeper‑specific note.

7) Rationale and risk preview
- Each recommendation includes 2–4 bullet reasons (favourite status, venue, form, momentum, cards) and a risk tag (safe/neutral/bold).

## Shouts (in‑play)

1) Momentum‑aware trigger
- Add a simple momentum proxy: shots for/against, final‑third entries, possession trend over last 10’. Combine with score trend to pick shouts.

2) Cooldowns and stacking
- Minimum interval between similar shouts (e.g., 8–10’); hard limit per half; visual countdown in UI.

3) Suppression rules (safety rails)
- Suppress aggressive shouts when: 2+ yellows on pitch; large lead late (prefer Calm/Focus); away under pressure (crowd effect).

4) Unit‑directed shouts
- Target DEF/MID/ATT when issues are localised (Focus DEF after chaotic defending; Demand More ATT when xThreat is low).

5) Opponent‑profile hints (lightweight)
- High press → suggest Calm/Focus when struggling to build; Low block → Praise after creating quality chances even without scoring.

6) Praise windows
- Short windows after positives (equaliser; 2–3 good chances; key block/save) with cooldown to prevent overuse.

7) Alternatives and confidence
- Return best shout + two alternates (safer vs braver) with pros/cons and cooldown indicator.

## Data & policy structure

- Policy bundles: favourite/underdog; home/away; importance tiers; derby flag. Select bundle per match.
- Matrices:
  - talk_matrix[phase][venue][fav][importance][score_state] -> tone candidates + weights.
  - gesture_matrix[tone][context] -> synergy score.
  - shout_matrix[score_trend][momentum][card_risk][fatigue] -> shout + cooldown.
- Disallow rules: context → blocked tones/shouts.
- Version fields and JSON Schema for validation.

## Signals to capture cheaply now

- Momentum proxy: shots on/off target Δ, final‑third entries, possession trend (last 10’).
- Card risk: yellows count, aggression proxy, “get stuck in” flag.
- Fatigue: minutes in last 7 days + stamina bands.
- Importance: user toggle (cup final, derby) until automated.
- Promise pressure: playing‑time target delta.

## UI affordances (minimal)

- Talk Composer: Whole team + Units + Individuals tabs; show recommendation, confidence, two alternatives, and “Why this”.
- Shout Bar: recommended shout, cooldown timer, unit dropdown, and two alternates.
- History chip: last talk/shout with outcome tag (used to drive escalation ladder).

## Tests we should add

- Golden scenarios:
  - Favourite/home 0–0 HT with good momentum → Encourage + positive gesture; suppress Disappointed.
  - Underdog/away 0–1 HT with low momentum → Calm/Focus; suppress Demand More.
  - 2–0 up at 80’ → suppress aggressive shouts; prefer Calm/Composed; cooldown respected.
  - Two booked defenders → Focus DEF; block Fire Up.
- Properties: cooldowns always respected; disallow rules enforced; synergy score non‑negative for chosen combo.

## Implementation map (for later)

- domain/models.py: extend Context (venue, importance, momentum, fatigue, last_talk/shout, unit metrics).
- data/policies.json & data/gestures.json: add matrices, ladders, cooldowns, disallow rules, bundle ids.
- domain/rules_engine.py: add momentum/suppression/escalation helpers; extend choose_inplay_shout and harmonize_talk_with_gesture.
- components/controls.py & components/cards.py: Talk Composer and Shout Bar surfaces; rationale chips; cooldown timer.
- tests/test_rules_engine.py & tests/test_schema.py: golden cases, schema validation.

---

Notes
- These ideas deliberately prioritise safety and clarity for users new to FM while giving advanced users a “bolder alternative” option.
- Start with policy‑driven logic (data files) so tuning doesn’t require code changes.