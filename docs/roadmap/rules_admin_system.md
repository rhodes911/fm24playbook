# Rules Admin System — Design Roadmap

Last updated: 2025-09-24

This document outlines a fully customizable, visual admin system to manage the Playbook’s rules without touching code. It makes rule behavior transparent, editable, versioned, and testable from within the app.

## Objectives

- Edit rules via UI (no code changes): templates, tone/gesture matrices, special overrides, and thresholds.
- See effects instantly with a live Preview on sample contexts.
- Validate against Football Manager (FM) availability constraints before applying.
- Versioning, diff, rollback, and import/export for safe iteration.
- Layering: ship a base rule pack, allow user overlays that merge on top.

## Scope of editable rules

- Tone Matrix
  - Allowed/disallowed tones by context (stage, venue, favourite_flag, score_state)
  - Weights/priority for tone selection
- Gesture Decision Matrix
  - Preferred gestures by stage/context; hard disallows
- Talk and Gesture-specific Templates
  - Phrase lists per stage and (optional) gesture; variable placeholders
- Stats Overlay Rules
  - Heuristics for adapting phrasing and suggesting shouts
  - Thresholds for momentum/pressure/control features
- Special Overrides
  - Promotion/title/cup/derby context keys with stage-specific phrases
- Reaction Adjustments and Nudges
  - Notes, suggestions triggered by reactions and history

## Data model (Rule Packs)

We externalize rules to JSON rule packs that the engine loads and merges.

- RulePack (top-level)
  - id: string (e.g., "base", "user")
  - version: semver (e.g., "1.0.0")
  - metadata: { name, description, author?, created_at }
  - precedence: number (higher wins on merge)
  - rules:
    - tone_matrix: { contexts[] → { allow?: string[], disallow?: string[], weights?: {tone:number} } }
    - gesture_matrix: { contexts[] → { prefer?: string[], disallow?: string[] } }
    - talk_templates: { stage → [ {gesture?: string, conditions?: [], phrase: string} ] }
    - stats_overlay: { thresholds, templates_by_stage, feature_params }
    - special_overrides: { stage → key → [phrases] }
    - reactions: { conditions[] → { notes: [string], adjustments?: {...} } }

- Context selector (reusable in all sections)
  - fields: { stage, venue, favourite_flag, importance, score_delta_range, minute_range, outcome?, opp_strength? }
  - operators: ==, !=, in, not_in, between, ≥, ≤ (limited DSL)

- Example path layout
  - data/rules/base.json         // shipped, read-only
  - data/rules/user.json         // user overlay, editable via UI
  - data/rules/drafts/*.json     // autosaved drafts while editing

## JSON Schema (high-level)

A JSON Schema validates rule packs on load and on save. Key points:

- ids and versions are required
- precedence must be integer
- stage, tone, gesture enums validate values
- conditions must only reference known Context fields and allowed operators
- phrase strings must not be empty; lists capped to reasonable sizes

(Implementation detail: keep a single schema file `data/rules/rulepack.schema.json`; validate in the loader.)

## Merge strategy

- Deep merge by section with deterministic precedence:
  - user overlay (precedence=100) > base (precedence=0)
- Arrays are concatenated then de-duplicated by a stable key (e.g., gesture+stage+phrase hash)
- Conflicts resolved in favor of higher precedence; warn in UI with a diff view

## Admin UI

- Access
  - Header toggle: Admin Mode (or query param `?admin=1`)
  - Visible only in local/dev by default; can be gated behind a config key

- Navigation (single page, sections accordion)
  1) Overview: active packs, precedence, validation state
  2) Tone Matrix Editor
     - Context grid builder; tone chips with allow/disallow/weight
  3) Gesture Matrix Editor
     - Stage/Context selectors; prefer/disallow lists with FM availability hints
  4) Templates Editor
     - Stage → (optional gesture) → phrases list; add/edit/delete; drag to prioritize
     - Placeholder help and linting (e.g., variables like {opponent})
  5) Stats Overlay
     - Threshold sliders and feature params; templates by stage
  6) Special Overrides
     - Keys like Promotion/Title/Cup → stage → phrases
  7) Reactions & Nudges
     - Condition builder + notes/adjustments editor
  8) Preview & Test
     - Context form; run engine; see output (tone, gesture, phrase, notes) side-by-side (current vs draft)
  9) Versioning & I/O
     - Save Draft, Validate, Diff vs Active, Promote to Active, Export, Import, Rollback

- FM Alignment and Validation
  - Inline checks: gesture availability per stage, disallowed tones
  - Errors block promotion to active; warnings allowed with badges

## Engine integration

- Loader (services/repository.py)
  - Load base and user packs; validate against schema
  - Merge with precedence; cache result and expose to engine
  - On failure, fall back to last-known-good and display a banner

- Rules engine (domain/rules_engine.py)
  - Replace hardcoded structures with data-driven accessors:
    - get_tone_options(context)
    - get_gesture_options(context)
    - get_templates(stage, gesture?, conditions?)
    - get_stats_overlay(stage)
    - get_special_overrides(stage, key)
    - get_reaction_adjustments(context)
  - Maintain code fallbacks if a section is missing

## Testing strategy

- Schema tests
  - Invalid packs are rejected with clear errors (bad enums, bad operators, missing fields)

- Merge tests
  - Base + overlay produce expected structures; conflicts resolved predictably

- Golden output tests
  - Known contexts → same recommendations using base pack
  - Overlay tweaks produce expected diffs

- UI tests (smoke)
  - Load, edit, validate, promote, rollback flows don’t error

- Property tests (optional)
  - Random contexts never violate FM constraints after validation

## Security and safety

- Never eval user input; use a simple, bounded condition DSL
- Enforce enum checks for stage/tone/gesture
- Limit sizes to prevent extreme memory growth
- Keep an offline backup of last-known-good pack (copy on promote)

## Migration plan

1) Externalize templates and special overrides (low risk)
2) Externalize tone/gesture matrices
3) Externalize stats overlay thresholds and templates
4) Externalize reaction adjustments
5) Remove legacy hardcodes after parity tests pass

## Performance

- Compile conditions to callable predicates and cache
- Cache merged packs in memory; reload on change
- Use shallow feature recomputation for preview to keep it snappy

## Example RulePack (abridged)

```json
{
  "id": "user",
  "version": "1.0.0",
  "metadata": {"name": "User Overlay", "description": "Local tweaks"},
  "precedence": 100,
  "rules": {
    "tone_matrix": {
      "contexts": [
        {
          "when": {"stage": "HalfTime", "venue": "away", "favourite_flag": false, "score_delta_range": [-99, -1]},
          "disallow": ["angry"],
          "weights": {"assertive": 0.7, "calm": 0.3}
        }
      ]
    },
    "gesture_matrix": {
      "contexts": [
        {
          "when": {"stage": "PreMatch", "favourite_flag": false},
          "prefer": ["Outstretched Arms"],
          "disallow": ["Point Finger"]
        }
      ]
    },
    "talk_templates": {
      "PreMatch": [
        {"gesture": "Outstretched Arms", "phrase": "Nobody expects us to get a result today, but stick to the plan."}
      ],
      "HalfTime": [
        {"phrase": "Raise your levels—this game is there for us if we sharpen up."}
      ]
    },
    "special_overrides": {
      "FullTime": {
        "Promotion": ["You’ve done it—soak it in and enjoy this moment."]
      }
    }
  }
}
```

## Rollout plan

- Phase 1 (UI + templates/overrides)
- Phase 2 (tone/gesture matrices)
- Phase 3 (stats overlay + thresholds)
- Phase 4 (reactions & nudges)
- Phase 5 (polish: diffs, rollback, import/export, guardrails)

## Success criteria

- Users can edit rules visually and validate against FM constraints.
- Engine reads merged packs producing predictable, test-covered outputs.
- Safe promotion/rollback flows without app restarts.
