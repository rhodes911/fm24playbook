import json
import streamlit as st
from services.repository import PlaybookRepository

st.set_page_config(page_title="Editor", page_icon="✏️")

st.title("✏️ Playbook Editor (Experimental)")

repo = PlaybookRepository()

try:
    with open(repo.data_dir / "playbook.json", "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    st.error(f"Failed to load playbook: {e}")
    st.stop()

content = st.text_area("Edit playbook.json", value=json.dumps(data, indent=2, ensure_ascii=False), height=400)

if st.button("Save"):
    try:
        new_data = json.loads(content)
        # simple validation via repository
        from domain.validators import validate_playbook
        validate_playbook(new_data)
        with open(repo.data_dir / "playbook.json", "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        st.success("Saved successfully.")
    except Exception as e:
        st.error(f"Save failed: {e}")