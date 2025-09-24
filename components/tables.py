"""
Tables component for matrix/cheat-sheet views.
"""
from __future__ import annotations

import streamlit as st
from typing import Any, Dict


def matrix(playbook_data: Dict[str, Any]) -> None:
    st.write("Cheat-sheet matrix (placeholder)")
    st.json(playbook_data)