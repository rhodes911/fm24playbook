# ⚽ FM24 Matchday Playbook — Streamlit App (Modular & Scalable)

> Instruction brief for Copilot. **No monolithic files.** Use reusable components, typed data models, and a clean separation between **data**, **domain logic**, **UI components**, and **app pages**.

See SPEC.md for the full raw specification and domain brief.

---

## 🗂️ Repo Structure

```
fm24playbook/
├─ app.py                    # thin bootstrapper (routes to /pages)
├─ pages/
│  ├─ 1_Session_Builder.py   # main interactive session builder (uses JSON rules)
│  └─ 2_Rules_Admin.py       # admin UI to edit normalized rules JSON
├─ components/               # UI-only, stateless widgets
│  ├─ controls.py            # sidebar/inline controls
│  ├─ cards.py               # recommendation cards (mentality/talk/shout/gesture)
│  ├─ banners.py             # status banners (e.g., "Underdog Away")
│  ├─ tables.py              # matrix views (cheat-sheet, reactions)
│  └─ icons.py               # small icon helpers (⚽ 🎙️ ✋ 📢 etc.)
├─ domain/                   # pure logic (no Streamlit calls)
│  ├─ models.py              # typed dataclasses / pydantic models
│  ├─ rules_engine.py        # decision engine (maps context → recommendations)
│  ├─ reactions.py           # player reaction UI hints/rules separation
│  ├─ presets.py             # predefined scenarios (Derby, Cup, 10 men, etc.)
│  └─ validators.py          # placeholder for future schema validation
├─ data/
│  ├─ gestures.json          # gestures taxonomy & mappings
│  ├─ policies.json          # engine policies and toggles
│  ├─ presets.json           # scenario presets (optional)
│  └─ rules/normalized/      # normalized JSON rule files edited by Rules Admin
│     ├─ base_rules.json
│     ├─ special_overrides.json
│     ├─ catalogs.json
│     ├─ statements.json
│     ├─ shouts.json
│     ├─ shout_rules.json
│     ├─ reaction_hints.json
│     ├─ reaction_rules.json
│     ├─ context_rules.json
│     ├─ stats_rules.json
│     └─ engine_config.json
├─ services/
│  └─ repository.py          # read/write helpers for JSON (future: API/DB)
├─ styles/
│  └─ theme.py               # theme tokens (spacing, font sizes)
├─ tests/
│  ├─ test_rules_engine.py   # unit tests for mapping logic
│  ├─ test_reactions.py      # unit tests for reactions handling
│  └─ test_tone_matrix.py    # unit tests for tone matrix behavior
├─ README.md                 # this file
└─ CONTRIBUTING.md           # conventions & PR guidelines
```

**Principles**
- **No UI code in `domain/`**; **no logic** in `components/`.
- **`data/` is declarative**: edit rules without touching code.
- **`rules_engine.py`** is the only place that understands the rule graph.

---

## 🧠 Core Concepts (Domain Language)

- **MatchStage**: `PreMatch | Early (0–25) | Mid (25–65) | HalfTime | Late (65–85) | VeryLate (85+) | FullTime`
- **Context**:
  - `FavStatus`: `Favourite | Underdog`
  - `Venue`: `Home | Away`
  - `ScoreState`: `Winning | Drawing | Losing`
  - `Special`: `Derby | Cup | Promotion | Relegation | DownTo10 | OpponentDownTo10 | None`
- **Outputs**:
  - **Mentality** (e.g., `Positive`, `Balanced`, `Cautious`, `Attacking`, `Very Attacking`, `Defensive`)
  - **TeamTalk** (string)
  - **Gesture** (from gestures taxonomy)
  - **Shout** (e.g., `Encourage`, `Demand More`, `Focus`, `Fire Up`, `Praise`, or `None`)
  - **Notes** (bullet tips)
- **Reactions** (overrides/adjustments): `Complacent | Nervous | LackingBelief | FiredUp | SwitchedOff`

---

## 🧾 Rules data layout (normalized JSON)

Rules are defined as small, focused JSON files under `data/rules/normalized/`. Highlights:

- `base_rules.json`: core recommendations by stage/favStatus/venue/scoreState
- `special_overrides.json`: contextual overrides (Derby, Cup, red cards)
- `reaction_rules.json`: engine adjustments driven by reactions (mentality deltas, merges)
- `reaction_hints.json`: UI-only hints for explaining reactions (not used by engine)
- `catalogs.json`, `statements.json`: tone/gesture catalogs and talk templates
- `shouts.json`, `shout_rules.json`: shout options and selection heuristics
- `context_rules.json`, `stats_rules.json`, `engine_config.json`: additional knobs

The rules engine loads these files directly; no single monolithic playbook.json is used.

## 🫳 Gestures Taxonomy (data/gestures.json)

```json
{
  "calm": ["Hands Together","Outstretched Arms"],
  "assertive": ["Point Finger","Hands on Hips"],
  "angry": ["Thrash Arms"],
  "motivational": ["Pump Fists"]
}
```

## 🧩 Domain Logic (rules_engine expectations)

**Inputs**: `Context(stage, favStatus, venue, scoreState, special[], reactions[])`

**Process**:
1. Load base rule for `(stage, favStatus, venue, scoreState)`; if no exact match, fall back to `(stage, favStatus)` then `(stage)`.
2. Apply special overrides (Derby/Cup/Promotion/Relegation/Red Cards).
3. Apply reactions adjustments per player reaction; merge notes; sum mentality deltas.
4. Clamp mentality to valid range; dedupe notes; return Recommendation.

**Outputs**: `Recommendation(mentality, teamTalk, gesture, shout, notes[])`

## 🎛️ UI Components (stateless contracts)

- `components.controls.sidebar(context_state)`: Inputs/returns a Context (stage, favStatus, venue, scoreState, special[], reactions[])
- `components.cards.recommendation_card(rec: Recommendation)`: Renders mentality, team talk, gesture, shout, notes
- `components.tables.matrix(playbook_data)`: Renders a scenario grid (cheat-sheet)
- `components.banners.context_banner(context)`: Small summary banner (e.g., "Underdog • Away • Drawing • Cup")

## 🔄 Pages Contracts

- `pages/1_Session_Builder.py`: Reads context (and latest snapshot) → calls `rules_engine.recommend(context)` → renders recommendation card + rationale
- `pages/2_Rules_Admin.py`: Admin UI to edit the normalized JSON files under `data/rules/normalized/`

## ✅ Testing Targets

- Mapping: Given contexts → expected recommendation (mentality, talk, gesture, shout)
- Reactions: Adjustments apply correctly and are composable
- Specials: Derby/Cup overrides merge without losing base notes

## 🧭 Contribution Conventions

- One rule per scenario; prefer specific → general fallback.
- Keep team talks and gestures short & directive.
- Use notes for nuance; avoid hardcoding logic outside `data/rules/normalized/`.
- Add unit tests when adding new rules or reactions.

## 🚀 Roadmap (Optional)

- Export PDF cheat-sheet of current matrix
- Multi-language talk templates
- User profiles (preferred tones, risk appetite)
  

## 🔧 Installation & Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   streamlit run app.py
   ```

3. Navigate to the different pages to explore the playbook functionality.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.