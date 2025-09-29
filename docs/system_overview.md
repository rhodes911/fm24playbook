# FM24 Playbook — System Overview

This document explains the end-to-end design of the FM24 Playbook: what it does, how it’s structured, how decisions are made, and how to tune or extend it. The system is JSON-driven, transparent, and safe-by-default, with optional ML assistance gated behind admin toggles.

## What the system does

- Guides team talks and in-play shouts using a configurable, table-styled rule engine.
- Detects Favourite/Underdog status and computes a granular matchup tier (Strong/Slight Favourite, Even, Slight/Strong Underdog) from data like table positions, form, venue, and live stats.
- Produces recommendations with explainable trace breadcrumbs so you can understand “why”.
- Provides an Admin UI to edit rules/config safely and a Session Builder UI to run match sessions and log telemetry.
- Optionally logs features to CSV and uses simple ML models to nudge suggestions, with strict guardrails.

## High-level architecture

- UI (Streamlit, pages/):
  - Session Builder: create and run a match session; see recommendations and trace; persist events.
  - Rules Admin: manage normalized rules, engine_config, and optional ML settings/validation.
  - Decision Tree (Graph/Simulator): visualize and simulate the decision logic with Tier/Edge and trace.
- Domain (domain/):
  - rules_engine.py: core decision pipeline (recommend, detect_fav_status, detect_matchup_tier).
  - models.py: dataclasses and enums for Context, Recommendation, enums for Venue, Stage, Tier, etc.
  - ml_assist.py: optional feature extraction and model helpers (safe by default).
- Services (services/):
  - session.py: Session lifecycle, event persistence, timezone-aware timestamps.
  - repository.py: data IO helpers.
  - telemetry.py: structured event logging.
- Data and Config (data/):
  - rules/normalized/: JSON rules and engine_config.json (weights/thresholds/toggles).
  - logs/: plays.jsonl, ml/features.csv (optional).
  - ml/: trained models and README.
- Tests (tests/): unit tests for rules engine behaviors, tiering, serialization, and talk/shout constraints.

## Data model (core types)

- Context: The input snapshot for a recommendation (stage, venue, score state, positions, form, live stats, auto/manual fav status, etc.).
- Recommendation: The output (team talk phrase, gesture, shout, mentality), plus trace/alternatives metadata.
- Enums: MatchStage, Venue, FavStatus, FavTier, ScoreState, Shout, etc.
- Rules JSON schema (normalized):
  - when: stage, fav/underdog conditions, optional tier, score state, venue, and any special flags.
  - then: talk/gesture/shout/mentality defaults; can be refined by heuristics.

## Engine: how a decision is made

1) Context preparation
- Auto-detect Favourite/Underdog (strictly enforced) if auto_fav_status is enabled.
- Compute (tier, edge, explanation) via detect_matchup_tier using advantage_model weights and caps.

2) Rule selection (JSON-driven)
- Match base rules by stage + conditions; if a rule specifies when.tier, it must match the computed tier.
- Apply specials/overrides (non-destructive and traceable).

3) Heuristics and safeguards
- Time/score clamping, live stats overlays, and tier-informed tweaks:
  - Talk intensity modulated by tier (e.g., Strong vs Slight Favourite nuance).
  - Even/SlightUnderdog with positive edge → supportive “push on” phrasing.
  - Late-game shout nuance (e.g., strong favourite drawing very late → Focus over Demand More).
- Guardrails:
  - No shouts during talk stages (PreMatch/HalfTime/FullTime) — shout remains None.
  - Praise and composure contexts protected; away favourite strictness enforced.

4) Explainability and trace
- Every meaningful step appends a trace note: rule match, tier/edge calc, overrides, heuristics, and ML nudges (if any).
- Trace is shown in UI and persisted with session events for analysis.

5) Optional ML assist (safe-by-default)
- Feature logging (opt-in): Writes CSV rows with inputs, chosen outputs, and A/B metadata.
- Training: scripts/train_ml_assist.py produces gesture.joblib and shout.joblib in data/ml/.
- Inference (opt-in): Per-stage toggles and a blending weight; re-ranks suggestions without breaking guardrails.
- Explainability: ML nudges noted in trace; “ml-meta” added to alternatives for logging/inspection.

## Configuration

- engine_config.json (data/rules/normalized/):
  - favourite_detection: thresholds and weights; strict away rules.
  - advantage_model: weights for positions, form, venue, live stats; cap; tier thresholds.
  - ml_assist: logging on/off and CSV path; inference enabled flag; model_dir; blend weight; per-stage toggles.
- Rules (data/rules/normalized/):
  - Base rules, specials, reactions — all table-styled JSON, no hardcoding.

## UI/Pages

- Session Builder (pages/1_Session_Builder.py)
  - Shows Tier: X • Edge: Y.YY on the Pre-Match card.
  - Displays the recommendation (talk/gesture/shout) with rationale and trace.
  - Timeline persists snapshots/events with tier/edge/trace in UTC.

- Rules Admin (pages/2_Rules_Admin.py)
  - Read-only by default; can enable editing to adjust favourite_detection and advantage_model.
  - ML assist section to toggle logging/inference, set model directory, weight, and per-stage switches.
  - Model status badge and a Quick Validation tool to compare rules output with ML probabilities.

- Decision Tree (Graph & Simulator)
  - Visualizes rule paths and simulates scenarios with auto-fav detection and Tier/Edge exposure.
  - Full trace expander for step-by-step reasoning.

## Persistence and telemetry

- Active session: data/sessions/active.json
- Archive: data/sessions/sessions.jsonl (append-only)
- Timezone-aware: all timestamps recorded with datetime.now(timezone.utc)
- Telemetry fields include tier, edge, and trace for later analysis.
- Optional ML CSV: data/logs/ml/features.csv (pre-ml and post-ml rows with ml-meta columns).

## Testing and quality gates

- Tests cover:
  - Tier boundaries and venue asymmetry
  - HalfTime “golden” behaviors (e.g., assertive family for strong favourites drawing)
  - Serialization of events with tier/edge/trace; UTC timestamp handling
  - Talk-stage shout is None (guardrail)
- VS Code Tasks:
  - Run unit tests (pytest)
  - Run app (Streamlit at http://localhost:8502)

## Extending the system

- Add or tune rules: edit JSON under data/rules/normalized/; use when.tier to gate rules by tier.
- Calibrate tiering: adjust advantage_model weights/caps/thresholds in engine_config.json.
- Evolve ML:
  - Turn on feature logging, gather data, train with scripts/train_ml_assist.py.
  - Validate with Admin tools, enable inference per-stage with a low weight, monitor A/B columns.
- Improve traceability: add fine-grained trace notes in rules_engine if you add heuristics.

## Key behaviors and edge cases

- Auto-detect favourite strictly enforced (manual input disabled and excluded when enabled).
- Away favourites are constrained by explicit away rules.
- Talk-stage shouts are intentionally None; in-play shouts only during match minutes.
- Missing stats handled robustly; weights allow you to downplay noisy signals early.

## File map (selected)

- app.py — Streamlit app bootstrap
- components/ — UI components (banners, cards, controls, tables)
- data/
  - rules/normalized/engine_config.json — advantage model, favourite detection, ML settings
  - rules/normalized/ — base/special/reaction rules
  - logs/plays.jsonl — gameplay logs
  - logs/ml/features.csv — optional ML feature logs
  - ml/ — trained models + README
- domain/
  - rules_engine.py — core recommendation engine, tiering, trace, ML assist hooks
  - models.py — core types and enums
  - ml_assist.py — optional ML helpers
- pages/
  - 1_Session_Builder.py — session workflow
  - 2_Rules_Admin.py — rules/config editor + ML tools
  - 3_Decision_Tree.py — decision visualization and simulator (if present)
- services/
  - session.py — session lifecycle and persistence (UTC)
  - repository.py, telemetry.py — IO and logging utilities
- tests/ — unit tests for engine, tiering, reactions, schema, tone matrix

## Summary

The FM24 Playbook is a transparent, JSON-driven decision engine with a practical UI for building sessions and tuning behavior. Tiering elevates nuance beyond Favourite/Underdog, tracing builds trust, and optional ML provides measured assistance without sacrificing safety or explainability.
