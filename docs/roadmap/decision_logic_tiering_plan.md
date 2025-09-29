# Decision Logic Overhaul: Tiered Advantage, Tracing, and Smarter Talks/Shouts

This plan upgrades the rules engine from coarse Favourite/Underdog into a granular, data‑aware system that better matches Football Manager’s nuance. It keeps everything JSON‑driven, stays compatible with Session Builder, and adds clear tracing so we can tune with confidence.

## Status at a glance

- [x] Fix Graph view rendering in Decision Tree (quoted hex colors, valid record labels)
- [x] Add granular matchup tiering (FavTier) and edge score via `detect_matchup_tier(context)`
- [x] Extend `engine_config.json` with `advantage_model` weights and tier thresholds
- [x] Surface Tier + Edge + explanation in Decision Tree Simulator
- [x] Keep backward compatibility; all tests passing
- [x] Add rule trace panel (Simulator + Session Builder)
- [x] Tier‑aware rule matching (optional `when.tier` in JSON rules)
 - [x] Tier‑informed shout/talk heuristics refinements
- [x] Admin editor for `advantage_model` and favourite detection config
- [x] Session Builder UI: show Tier/Edge on Pre‑Match card and in in‑play previews; log tier/edge in events
- [x] Test suite expansion for tier boundaries and venue effects
 - [ ] (Optional) ML assist for re‑ranking with explainability (offline training; guardrails)

---

## Objectives

- Increase decision granularity beyond Favourite/Underdog (strong/slight/even bands).
- Use the data we already collect (positions, form, venue, live stats) to compute an “edge score” that informs tone/gesture/shout selection.
- Maintain JSON‑first design and add transparent tracing for debugging calibration.
- Ensure seamless compatibility with Session Builder: no breaking changes, clear UI additions, and persisted telemetry for later analysis.

## Non‑goals (for this phase)

- Replacing rules with a black‑box ML model. We’ll use ML only as an optional re‑ranking signal after rules, with explainable outputs.
- Changing the existing Context API surface in a breaking way.

---

## Current state (baseline)

- Engine functions: `recommend(ctx)` and `detect_fav_status(ctx)`.
- Config: `engine_config.json` controls favourite detection; now also contains `advantage_model` (weights, caps, tier thresholds).
- New: `FavTier` enum and `detect_matchup_tier(ctx)` compute a granular tier with a numeric edge score and a human explanation string.
- Decision Tree page: Graph view fixed; Simulator view added; Simulator now shows auto‑fav detection and tier/edge.
- Tests: 11/11 passing.

---

## Design: Tiered Advantage Model

- Features used (all optional, robust to missing values):
  - Table: position delta (scaled so ~4 places ≈ 1 point)
  - Form: W=3, D=1, L=0 across last 5, delta scaled (~5 pts ≈ 1 point)
  - Venue: home bonus, away penalty
  - Live stats: xG delta, shots delta, possession bias
  - Stage‑aware modifiers (later addition): reduce live stats weight early, increase late
- Config (`data/rules/normalized/engine_config.json`):
  - `advantage_model`: weights, cap, and tier thresholds mapping score → tier bands.
  - Tunable without code changes.

---

## Step‑by‑step delivery

### 1) Tracing and Transparency

- [x] Add a “Trace” object from `recommend()` that lists:
  - Base rule matched (id/index) and why (stage/fav/venue/score/special matches)
  - Specials applied and their overrides (talk/gesture/shout/mentality)
  - Time/score and live‑stats heuristic notes (with triggering conditions)
  - Reactions adjustments applied
- [x] Decision Tree Simulator: new expander shows the full trace
- [x] Session Builder: small “Why this” expander includes the same trace

### 2) Tier‑aware Rules (non‑breaking)

- [x] Extend rule schema to support optional `when.tier: FavTier | FavTier[]`
- [x] Engine rule matching: when `tier` present, require match (else fallback to existing behaviour)
- [x] Add a couple of exemplar tier‑aware rules in `base_rules.json` (e.g., SlightFavourite + Drawing at HalfTime → assertive talk, vs Even + Drawing → supportive calm)
- [x] Keep all legacy rules intact so behaviour is unchanged where tier is unspecified

### 3) Tier‑informed Heuristics

 - [x] Shouts:
  - SlightUnderdog drawing late → Encourage
  - StrongFavourite drawing very late → Focus (composure) rather than Demand More
  - Even with positive edge (xG/pos/session momentum) → bias toward “push on” calm lines
 - [x] Talk phrase selection:
  - Tone intensity modulated by tier (SlightFavourite ≠ StrongFavourite)
  - When Even/SlightUnderdog but edge>0, prefer supportive perseverance phrasing

### 4) Admin Editor for Config

- [x] Add a guarded (read‑only by default) Admin UI to edit `engine_config.json`:
  - favourite_detection (thresholds/weights/away rules)
  - advantage_model (weights, cap, tier thresholds)
- [x] Validate and preview the effect (simulate a few canonical scenarios inline)

### 5) Session Builder Integration (primary requirement)

- [x] Pre‑Match card: show `Tier: X • Edge: Y.YY` below the status chip
- [x] Simulator parity: use the same `detect_matchup_tier(ctx)` in previews
- [x] In‑play shout preview: include Tier/Edge in the rationale
- [x] Timeline/events: persist `tier` and `edge` in snapshot/decision payloads for analytics
- [x] Strict auto‑fav remains enforced (manual status disabled when auto)

### 6) Tests

- [x] Unit tests for tier boundaries (even_lo/even_hi) and venue asymmetry
 - [x] Golden tests for HalfTime recommendations across tier bands
- [x] Serialization tests for events containing `tier`/`edge`

### 7) (Optional) ML Assist

 - [x] Feature logger (opt‑in): write features + chosen outputs to a CSV for offline training (toggle and path in Engine Config)
 - [ ] Train a simple, explainable model (logistic regression / gradient boosting) predicting tone/gesture/shout distributions
 - [ ] Inference: use ML only to re‑rank alternatives; never override guardrails
 - [ ] Expose explanation (coefficients/feature importance) in the trace
 - [x] Toggle in Admin with fallback to rules‑only

---

## Compatibility with Session Builder

- No breaking changes: `recommend(ctx)` signature unchanged; `FavTier` is additive.
- New data displayed (Tier/Edge) in Pre‑Match and in‑play previews; not required for saving.
- Events can optionally store `{ tier, edge }` inside `payload`; reading remains tolerant.
- Auto‑detect favourite continues to work and stays strictly enforced when enabled.

---

## File changes (planned)

- `domain/models.py`
  - [x] Add `FavTier` enum.
  - [x] Extend `RuleCondition` to support optional `tier` (single or list) for rule matching.
- `domain/rules_engine.py`
  - [x] Implement `detect_matchup_tier(context)` using `advantage_model`.
  - [x] Return or attach a detailed “trace” object; surface in UI.
  - [x] Apply tier‑aware rule matching; tier‑informed shout/talk tweaks.
- `data/rules/normalized/engine_config.json`
  - [x] Add `advantage_model` weights and thresholds.
- `data/rules/normalized/base_rules.json`
  - [x] Add exemplar rules using `when.tier` (non‑breaking).
- `pages/3_Decision_Tree.py`
  - [x] Fix Graph; add Simulator; show Tier/Edge and explanation.
  - [x] Add trace expander; add quick scenario presets.
- `pages/1_Session_Builder.py`
  - [x] Show Tier/Edge on Pre‑Match card and in shout/talk previews.
  - [x] Persist tier/edge in snapshot/decision payloads.
- `tests/`
  - [x] Add tier boundary tests; venue strictness tests; UI serialization tests.

---

## How to run

- Unit tests

```powershell
# VS Code Task
# Run unit tests
```

- App (Streamlit)

```powershell
# VS Code Task
# Run app (Streamlit)
# App will open at http://localhost:8502
```

---

## Quality gates

- Build/lint: no syntax errors; typing preserved.
- Tests: existing suite unchanged; new tier tests added and passing (20/20).
- Manual smoke: Decision Tree → Simulator produces sensible Tier/Edge; Session Builder shows Tier/Edge without breaking workflows.

---

## Risks and mitigations

- Overfitting weights to a small set of examples → keep config‑driven; add trace for explainability; expand tests across scenarios.
- UI clutter → use chips and expanders; keep default collapsed.
- ML path complexity → keep optional and explainable; start with logging and shadow evaluation before enabling in decisions.

---

## Completion criteria

- Tier/Edge visible and correct in both Simulator and Session Builder.
- Rules can optionally target tiers; shout/talk heuristics respect tiers.
- Trace is available to explain any recommendation.
- Admin can safely tune thresholds/weights with preview.
- Tests cover key boundaries; all pass.

---

## Notes

- The existing Favourite/Underdog is still respected; tiering augments nuance without removing simplicity.
- Away strictness stays enforced; tiers are calibrated by venue automatically through weights.
