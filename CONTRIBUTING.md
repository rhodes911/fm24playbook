# Contributing

- One rule per scenario; prefer specific → general fallback.
- Keep team talks and gestures short & directive.
- Use notes for nuance; avoid hardcoding logic outside `data/playbook.json`.
- Add or update unit tests when adding new rules or reactions.
- No UI code in `domain/`; no logic in `components/`.

## Dev setup

- Install deps: `pip install -r requirements.txt`
- Run tests: `pytest -q`
- Run app: `streamlit run app.py`
