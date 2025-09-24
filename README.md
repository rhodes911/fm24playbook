# ⚽ FM24 Matchday Playbook — Streamlit App (Modular & Scalable)

> Instruction brief for Copilot. **No monolithic files.** Use reusable components, typed data models, and a clean separation between **data**, **domain logic**, **UI components**, and **app pages**.

See SPEC.md for the full raw specification and domain brief.

---

## 🗂️ Repo Structure

```
fm24playbook/
├─ app.py                    # thin bootstrapper (routes to /pages)
├─ pages/
│  ├─ 1_Playbook.py         # main interactive playbook page
│  ├─ 3_Editor.py           # (optional) admin editor for playbook data
│  └─ 4_About.py            # credits, how-to, change-log
├─ components/              # UI-only, stateless widgets
│  ├─ controls.py           # sidebar controls (selectors)
│  ├─ cards.py              # recommendation cards (mentality/talk/shout/gesture)
│  ├─ banners.py            # status banners (e.g., "Underdog Away")
│  ├─ tables.py             # matrix views (cheat-sheet, reactions)
│  └─ icons.py              # small icon helpers (⚽ 🎙️ ✋ 📢 etc.)
├─ domain/                  # pure logic (no Streamlit calls)
│  ├─ models.py             # typed dataclasses / pydantic models
│  ├─ rules_engine.py       # decision engine (maps context → recommendations)
│  ├─ reactions.py          # player reaction fixers (lack belief, nervous, etc.)
│  ├─ presets.py            # predefined scenarios (Derby, Cup, 10 men, etc.)
│  └─ validators.py         # schema validation for playbook JSON
├─ data/
│  ├─ playbook.json         # single source of truth for rules (see schema)
│  ├─ gestures.json         # gestures taxonomy & mappings
│  └─ presets.json          # scenario presets (optional, not used by UI now)
├─ services/
│  └─ repository.py         # read/write layer for JSON (future: API/DB)
├─ styles/
│  └─ theme.py              # theme tokens (spacing, font sizes)
├─ tests/
│  ├─ test_rules_engine.py  # unit tests for mapping logic
│  ├─ test_reactions.py     # unit tests for reactions fixer
│  └─ test_schema.py        # schema validation tests
├─ README.md                # this file
└─ CONTRIBUTING.md          # conventions & PR guidelines
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

## 🧾 Playbook Data Schema (JSON)

**File**: `data/playbook.json`

```json
{
  "$schema": "https://example.com/fm24-playbook.schema.json",
  "version": "1.0.0",
  "gestures": ["Point Finger","Hands on Hips","Outstretched Arms","Hands Together","Pump Fists","Thrash Arms"],
  "rules": [
    {
      "when": {
        "stage": "PreMatch",
        "favStatus": "Favourite",
        "venue": "Home"
      },
      "recommendation": {
        "mentality": "Positive",
        "teamTalk": "We should be winning this — go out and show why.",
        "gesture": "Point Finger",
        "shout": "None",
        "notes": ["Set expectations without overhyping","Individually tell strikers: You can make the difference (Pump Fists)"]
      }
    },
    {
      "when": {
        "stage": "PreMatch",
        "favStatus": "Underdog",
        "venue": "Away"
      },
      "recommendation": {
        "mentality": "Cautious",
        "teamTalk": "No pressure, go out and enjoy it.",
        "gesture": "Outstretched Arms",
        "shout": "None",
        "notes": ["Remove fear, frame opportunity","Call out complacent players individually (Hands on Hips)"]
      }
    }
  ],
  "reactions": [
    {
      "reaction": "Complacent",
      "adjustment": {
        "teamTalk": "Don't get complacent — keep working.",
        "gesture": "Point Finger",
        "shout": "Demand More",
        "mentalityDelta": 0,
        "notes": ["Challenge effort, not ability","Avoid over-praise"]
      }
    },
    {
      "reaction": "Nervous",
      "adjustment": {
        "teamTalk": "I've got faith in you.",
        "gesture": "Outstretched Arms",
        "shout": "Encourage",
        "mentalityDelta": -1,
        "notes": ["Reduce pressure","Keep structure (Balanced/Cautious)"]
      }
    }
  ],
  "special": [
    {
      "tag": "Derby",
      "overrides": {
        "preMatch": {"teamTalk":"Do it for the fans.","gesture":"Pump Fists"},
        "halfTimeLead": {"teamTalk":"Don't let this slip.","gesture":"Point Finger"},
        "fullTimeWin": {"teamTalk":"You've made the fans proud.","gesture":"Hands Together"}
      }
    },
    {
      "tag": "Cup",
      "overrides": {
        "preMatchUnderdog": {"teamTalk":"No pressure, enjoy it.","gesture":"Outstretched Arms"},
        "halfTimeLosing": {"teamTalk":"This is your chance to make history.","gesture":"Pump Fists"},
        "fullTimeWin": {"teamTalk":"Brilliant, enjoy the moment.","gesture":"Hands Together"}
      }
    }
  ]
}
```

**Note**: `mentalityDelta` uses a scale for internal mapping: `Defensive(-2)`, `Cautious(-1)`, `Balanced(0)`, `Positive(+1)`, `Attacking(+2)`, `VeryAttacking(+3)`. The rules engine converts base mentality ± delta → final mentality (clamped to range).

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

- **pages/1_Playbook.py**: Read Context via sidebar → Load playbook.json, gestures.json → Call rules_engine.recommend(context) → Render recommendation_card + hints/notes
- **pages/3_Editor.py** (optional, can be feature-flagged): Simple UI to add/edit rules → writes back to data/playbook.json

## ✅ Testing Targets

- **Mapping**: Given contexts → expected recommendation (mentality, talk, gesture, shout)
- **Reactions**: Adjustments apply correctly & are composable
- **Specials**: Derby/Cup overrides merge without losing base notes
- **Schema**: playbook.json validated pre-run; fail fast with helpful error

## 🧭 Contribution Conventions

- One rule per scenario; prefer specific → general fallback.
- Keep team talks and gestures short & directive.
- Use notes for nuance; avoid hardcoding logic outside playbook.json.
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