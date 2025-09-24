# Single-page Match Session Builder — Roadmap

Last updated: 2025-09-24

This document proposes a single-page “Session Builder” workflow for logging one complete match session from Pre-Match through Full-Time. It replaces sidebar-driven ad-hoc inputs with a guided, history-aware timeline powered by snapshots.

## Goals

- Single-page flow: capture an entire match session without sidebar dependency.
- End-to-end record: Pre-Match → First Half → Half-Time → Second Half → Full-Time → Submit.
- History-aware engine: decisions adapt to how the match developed, not just the current state.
- Preserve FM alignment: gestures and tones reflect Football Manager’s stage/gesture availability.
- Reliable persistence: draft autosave, resume, and immutable submitted sessions.

## Constraints and non-goals

- No multi-page nav; one page owns the entire session flow.
- Maintain the current unit tests (extend but don’t regress behavior).
- Reuse existing rules, templates, and overlays; extend with history features carefully.
- External service calls out of scope; local persistence only.

---

## UX blueprint (single page)

- Header
  - Match metadata: opponent, venue (home/away), favourite/underdog, competition, importance.
  - Controls: Start, Save Draft, Resume Last, Submit Session.

- Stacked stage cards (top → bottom):
  1) Pre-Match
     - Metadata confirmation
     - Recommended talk (tone + gesture + phrase)
     - FM availability hints and validation
     - Lock Decision
  2) First Half (In-Play)
     - Snapshot form (minute, score, stats)
     - Add Snapshot → recompute history features
     - Suggest shout → quick-add to timeline
     - Stage timeline (FH entries)
  3) Half-Time
     - Auto-pulled HT snapshot (45')
     - Recommended talk (history-aware)
     - Lock Decision
  4) Second Half (In-Play)
     - Same as First Half with a SH timeline
  5) Full-Time
     - Final snapshot (90+ or 120)
     - Recommended talk (history-aware)
     - Lock Decision

- Timeline rendering
  - Ordered list of events with chips like: [25' Snapshot], [27' Shout: Encourage], [HT Decision].
  - Hover or expand for details and derived metrics highlights.

- Footer
  - Save Draft (autosaves are also on), Submit Session, Start New Session.

---

## Data model

We propose a session-centric, append-only timeline with derived aggregates.

- Session
  - id: string (uuid)
  - created_at: ISO datetime
  - version: string (for migrations)
  - match_meta: { opponent, venue, favourite_flag, importance, competition }
  - timeline: [Event]  // ordered by (minute, seq)
  - stage_decisions: { prematch?: Decision, halftime?: Decision, fulltime?: Decision }
  - derived: { last_computed_at, params, feature_summaries }
  - outcome?: { final_score_for, final_score_against, xg_for, xg_against, notes? }
  - status: 'draft' | 'submitted'

- Event
  - type: 'snapshot' | 'shout' | 'decision' | 'note'
  - minute: number
  - seq: number  // tie-breaker for identical minutes
  - payload: Snapshot | Shout | Decision | Note

- Snapshot
  - minute: number
  - score_for: number
  - score_against: number
  - possession_pct?: number
  - shots_for?: number
  - shots_against?: number
  - shots_on_target_for?: number
  - shots_on_target_against?: number
  - xg_for?: number
  - xg_against?: number
  - flags?: { injury?: boolean, red_card_for?: boolean, red_card_against?: boolean }
  - notes?: string

- Shout (suggested or user-chosen)
  - kind: 'Encourage' | 'Demand More' | 'Focus' | 'Calm Down' | ...
  - gesture?: string  // if FM-aligned shouts later
  - note?: string

- Decision (stage-locked talk)
  - stage: 'PreMatch' | 'HalfTime' | 'FullTime'
  - tone: string
  - gesture: string
  - phrase: string
  - fm_alignment: { allowed_gestures: string[], disallowed_tones: string[] }
  - notes?: string

- Storage
  - Drafts: autosaved records (e.g., data/sessions/drafts/)
  - Submissions: append to data/sessions/sessions.jsonl (already present)

---

## History features (derived from snapshots)

Let t denote the current minute of the latest snapshot.

- State at t
  - Game state: $g_t = \text{score\_for} - \text{score\_against}$
  - xG differential: $\Delta xG_t = xG\_{for} - xG\_{against}$

- Momentum (slope of recent xG differential)
  - Window size k (default 10 minutes)
  - $$ m_t = \text{slope}\big(\Delta xG\_{[t-k, t]}\big) $$

- Pressure index (defensive pressure from opponent)
  - $$ P_t = \alpha\,\text{rate}(\text{SOT}_\text{against}) + \beta\,\text{rate}(xG_\text{against}) $$
  - Start with $\alpha = 1, \beta = 3$ (quality > volume)

- Control trend (possession drift using EWMA)
  - Let $pos_t$ be possession at t
  - $$ C_t = pos_t - \operatorname{EWMA}_{[t-k, t]}(pos; \lambda) $$

- Conversion efficiency (finishing vs expected)
  - $$ E_t = (\text{goals\_for to } t) - \gamma\,(xG\_{for\text{ to } t}),\quad \gamma \approx 1 $$

- Comeback viability (time-adjusted xG pace vs goals needed)
  - Remaining time $r = T - t$ (T=90 or 120)
  - Goals needed $h = \max(0, -g_t + 1)$
  - $$ V_t = \hat{xG\_\text{rate}}\cdot r - h\,\theta, \quad \theta \approx 0.7 \; \text{xG/goal} $$
  - $V_t < 0$ → push more assertively; $V_t > 0$ → maintain/control

These features augment the current rules engine inputs to produce more contextually correct talks and shouts.

---

## Engine behavior with history

- Pre-Match
  - Use existing templates and matrices, cache pre-match profile.

- In-Play shout suggestions
  - If $m_t$ high and $g_t \le 0$: Encourage/Demand More (per availability)
  - If $P_t$ high while leading late: Focus/Calm to consolidate
  - If $C_t$ negative and favourite: calming note or keep-ball message
  - If $E_t$ very negative: reassure finishing or improve shot quality

- Half-Time talk (history-aware)
  - Losing with positive $m_t$ and $V_t \approx 0$: assertive but not praise
  - Losing with negative $m_t$ and high $P_t$: firmer reset within FM-allowed gestures
  - Drawing with positive $m_t$ and negative $E_t$: calm encouragement, composure focus

- Full-Time talk
  - Consider $E_t$, $g_t$, importance; special overrides (Promotion/title) still win

- Lock semantics
  - Locked decisions are authoritative; overlays/heuristics won’t auto-overwrite
  - Explicit “Edit decision” required to change a locked stage

---

## Validation and FM alignment

- Per-stage checks ensure gestures/tones are valid for context and stage.
- Inline warnings and suggested alternatives.
- Submission requires: PreMatch, HalfTime, FullTime decisions; final snapshot at 90+ (or 120) minutes; no validation errors.

---

## Persistence and lifecycle

- Autosave draft on Add Snapshot, Add Shout, Lock Decision.
- Submit consolidates draft to a single immutable sessions.jsonl entry.
- Resume loads latest draft by id; Start New clears current state.
- Version on each session to allow future migrations.

---

## Testing strategy

- Unit tests
  - Feature calculators: slopes, EWMA, rates, windowing edge cases
  - Engine rules: FM alignment invariants (e.g., angry disallowed at HT underdog away)

- Integration tests
  - Golden sessions: timeline fixtures → canonical JSONL output
  - Resume/submit flow, lock/edit semantics, autosave cadence

- Property-based tests
  - Random snapshot sequences preserve invariants and produce valid recommendations

- UI smoke tests
  - Streamlit smoke harness: ensures render + common interactions don’t error

---

## Phased delivery plan

- Phase A — Snapshot skeleton (0.5–1d)
  - Snapshot model and timeline events in memory (st.session_state)
  - UI: Add Snapshot form, timeline list, autosave draft
  - Acceptance: snapshots appear, order stable, draft persists

- Phase B — History features (0.5–1d)
  - Implement $m_t, P_t, C_t, E_t, V_t$ with tunables
  - Acceptance: derived metrics visible; unit tests green

- Phase C — In-Play shouts (0.5–1d)
  - Recommend shouts from latest snapshot + features
  - Acceptance: quick-add shouts appear in timeline; heuristics unit-tested

- Phase D — Stage decisions (1–1.5d)
  - PreMatch, HalfTime, FullTime lock flows wired to rules_engine
  - Ensure overlays stop post-lock; allow explicit edit
  - Acceptance: decisions locked, timeline reflects stages correctly

- Phase E — Validation + Submit (0.5–1d)
  - FM alignment checks per stage, submission gate criteria
  - Write to sessions.jsonl; draft cleared
  - Acceptance: invalid sessions blocked; valid sessions recorded immutably

- Phase F — Externalization + polish (optional, 1–2d)
  - Move gesture/stat overlay templates to data/ with schema
  - Feature flags: “Adapt phrasing using live stats,” aggressiveness knobs

---

## Contracts (tiny)

- Snapshot input
  - minute:int, score_for:int, score_against:int,
  - possession_pct?:float, shots_for/against?:int, shots_on_target_for/against?:int,
  - xg_for/against?:float, notes?:string

- Event output (timeline)
  - { type:'snapshot'|'shout'|'decision', minute, seq, payload }

- Decision output
  - { stage, tone, gesture, phrase, fm_alignment, notes? }

---

## Edge cases

- Out-of-order minutes: allow; timeline sorts by (minute, seq); show a badge
- Duplicate-minute snapshots: keep both; derived metrics use the latest by seq
- Missing stats fields: compute with available values; mark confidence low
- Extra time: T becomes 120; windows adapt
- Red cards/injuries (future): adjust pressure/control heuristics weighting

---

## Risks and mitigations

- Overwriting locked decisions
  - Mitigation: lock is authoritative; overlays disabled post-lock

- Data loss on refresh
  - Mitigation: autosave on each event; Resume draft; optional JSON download

- Complexity creep
  - Mitigation: feature flags for advanced overlays; ship core path first

---

## Success criteria

- End-to-end session built on a single page without sidebar.
- FM alignment warnings prevent invalid gesture/tone combinations.
- Submitted sessions are reproducible, human-readable, and covered by tests.

---

## Immediate next steps

1) Scaffold Session Builder UI (stacked stage cards) in `app.py` or `pages/1_Playbook.py`.
2) Implement Snapshot model + timeline in `services/session.py` (draft autosave to data/sessions/).
3) Wire current rules_engine to PreMatch decision; show lock and timeline entry.
4) Add derived metrics (m_t, P_t, C_t, E_t, V_t) with tests.
5) Iterate with In-Play shout suggestions, then HT/FT decisions.

---

## Appendix — Example session JSONL entry (concept)

```json
{
  "id": "c1fd7a3d-3c4b-4f88-8f2e-0ad1c2b3e4f5",
  "created_at": "2025-09-24T19:15:31Z",
  "version": "1.0.0",
  "match_meta": {"opponent":"Arsenal","venue":"away","favourite_flag":false,"importance":"league","competition":"Premier League"},
  "timeline": [
    {"type":"decision","minute":0,"seq":0,"payload":{"stage":"PreMatch","tone":"calm","gesture":"Outstretched Arms","phrase":"Nobody expects us to get a result today, but stick to the plan and work hard.","fm_alignment":{"allowed_gestures":["Outstretched Arms"],"disallowed_tones":["angry"]}}},
    {"type":"snapshot","minute":25,"seq":0,"payload":{"minute":25,"score_for":0,"score_against":1,"possession_pct":48,"shots_for":3,"shots_against":6,"shots_on_target_for":1,"shots_on_target_against":3,"xg_for":0.29,"xg_against":0.78}},
    {"type":"shout","minute":27,"seq":0,"payload":{"kind":"Encourage","note":"Momentum rising despite trailing"}},
    {"type":"decision","minute":45,"seq":0,"payload":{"stage":"HalfTime","tone":"assertive","gesture":"Hands On Hips","phrase":"You’re better than this—raise your levels and turn it around.","fm_alignment":{"allowed_gestures":["Hands On Hips","Point Finger"],"disallowed_tones":["angry"]}}},
    {"type":"snapshot","minute":70,"seq":0,"payload":{"minute":70,"score_for":1,"score_against":1,"possession_pct":52,"shots_for":9,"shots_against":10,"shots_on_target_for":4,"shots_on_target_against":5,"xg_for":1.18,"xg_against":1.25}},
    {"type":"shout","minute":78,"seq":0,"payload":{"kind":"Focus","note":"Leading late under pressure"}},
    {"type":"decision","minute":90,"seq":1,"payload":{"stage":"FullTime","tone":"calm","gesture":"Hands Together","phrase":"Well done—professional performance. Recover well and go again.","fm_alignment":{"allowed_gestures":["Hands Together"],"disallowed_tones":[]}}}
  ],
  "derived": {"last_computed_at":"2025-09-24T19:16:44Z","params":{"k":10,"alpha":1,"beta":3,"lambda":0.3,"gamma":1.0,"theta":0.7}},
  "outcome": {"final_score_for":2, "final_score_against":1, "xg_for":1.7, "xg_against":1.4},
  "status": "submitted"
}
```

---

Notes
- Drafts: continue to use `data/sessions/sessions.jsonl` for submitted sessions and a parallel `data/sessions/drafts/` folder for in-progress sessions (filename = session id).
- Keep the existing `rules_engine` contracts; augment with history features without breaking current tests.
