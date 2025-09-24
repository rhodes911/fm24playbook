"""
Context banner component to summarize current selection.
"""
from __future__ import annotations

import streamlit as st
from domain.models import Context


def context_banner(ctx: Context) -> None:
    st.markdown(
        f"<div class='context-banner'><strong>Context:</strong> {str(ctx)}</div>",
        unsafe_allow_html=True,
    )