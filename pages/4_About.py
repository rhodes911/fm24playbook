import streamlit as st

st.set_page_config(page_title="About", page_icon="ℹ️")

st.title("ℹ️ About FM24 Matchday Playbook")

st.markdown(
    """
This app provides in-match guidance for Football Manager 2024.

- Modular architecture: data-driven rules, testable domain logic, and simple UI components.
- Update `data/playbook.json` to change recommendations without code edits.
- Use the Editor page to experiment safely (validation included).

Contributions welcome! See CONTRIBUTING.md for conventions.
    """
)