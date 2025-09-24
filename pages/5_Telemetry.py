import json
from pathlib import Path
import streamlit as st

LOG_FILE = Path(__file__).resolve().parents[1] / "data" / "logs" / "plays.jsonl"

st.set_page_config(page_title="Telemetry", page_icon="📊")
st.title("📊 Telemetry")

if not LOG_FILE.exists():
    st.info("No telemetry yet — interact with the Playbook to generate logs.")
    st.stop()

count = 0
rows = []
with LOG_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        try:
            rows.append(json.loads(line))
            count += 1
        except Exception:
            pass

st.caption(f"Loaded {count} events")
rows = list(reversed(rows))

for r in rows[:200]:
    with st.expander(f"{r.get('ts')} • {r.get('event')} • {r.get('recommendation',{}).get('mentality','')} • {r.get('context',{}).get('stage','')}"):
        st.json(r)
