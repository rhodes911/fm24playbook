"""
FM24 Matchday Playbook - Main Application Entry Point

This is a thin bootstrapper that configures Streamlit and routes to pages.
All business logic is contained in the domain/ and components/ modules.
"""

import streamlit as st
from pathlib import Path

# Configure Streamlit page
st.set_page_config(
    page_title="⚽ FM24 Matchday Playbook",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stSelectbox > div > div > select {
        background-color: #f0f2f6;
    }
    .recommendation-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        background-color: #fafafa;
    }
    .context-banner {
        background-color: #e8f4f8;
        border-left: 4px solid #1f77b4;
        padding: 0.5rem 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """Main application entry point"""
    st.title("⚽ FM24 Matchday Playbook")
    st.markdown("### Use the Playbook page from the sidebar to get recommendations.")
    st.info("""
    Welcome to the FM24 Matchday Playbook! This tool helps you make tactical decisions during matches.
    
    📋 **Playbook** - Get recommendations based on match context.
    """)
    
    # Display current project structure for reference
    with st.expander("📁 Project Structure", expanded=False):
        st.code("""
fm24playbook/
├─ app.py                    # Main entry point
├─ pages/                    # Streamlit pages (1_Playbook only)
├─ components/               # UI components
├─ domain/                   # Business logic
├─ data/                     # JSON data files
├─ services/                 # Data access layer
├─ styles/                   # Theming
└─ tests/                    # Unit tests
        """, language="text")

if __name__ == "__main__":
    main()