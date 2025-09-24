import json
import streamlit as st
from pathlib import Path

st.title("🛠️ Rules Admin")
st.caption("Edit and preview rules via visual tools. This is a stub; editors will ship in phases.")

rules_dir = Path(__file__).resolve().parents[1] / "data" / "rules"
base_fp = rules_dir / "base.json"
user_fp = rules_dir / "user.json"

st.subheader("Active Rule Packs")
st.code(str(rules_dir))

cols = st.columns(2)
with cols[0]:
    st.markdown("**Base Pack (read-only)**")
    if base_fp.exists():
        st.json(json.loads(base_fp.read_text(encoding="utf-8")))
    else:
        st.info("No base.json found yet.")
with cols[1]:
    st.markdown("**User Overlay**")
    if user_fp.exists():
        st.json(json.loads(user_fp.read_text(encoding="utf-8")))
    else:
        st.info("No user.json found yet. Create via future editors.")

st.divider()
st.subheader("Next steps")
st.markdown("- Add editors for tone/gesture matrices, templates, overlays, special overrides, and reactions.")
st.markdown("- Live preview engine output for a sample context.")
