import json
import streamlit as st
from pathlib import Path

from services.repository import PlaybookRepository
from domain.models import (
    MatchStage, ScoreState,
)

st.title("🧱 Rules Admin — Minimal Tables")
st.caption("Only the three granular tables: Gestures, Statements, and Gesture↔Statements links.")

st.divider()
repo = PlaybookRepository()
try:
    gestures_map = repo.load_gestures()
except Exception:
    gestures_map = {}

st.divider()
st.subheader("Rules Setup (from scratch)")
st.caption("Edit only: Gestures, Statements, and Gesture↔Statements links.")

# Normalized storage paths
norm_dir = Path(__file__).resolve().parents[1] / "data" / "rules" / "normalized"
norm_dir.mkdir(parents=True, exist_ok=True)
catalogs_fp = norm_dir / "catalogs.json"
statements_fp = norm_dir / "statements.json"
gesture_statements_fp = norm_dir / "gesture_statements.json"

def _load_json_or(default: dict, fp: Path) -> dict:
    try:
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return json.loads(json.dumps(default))

# Defaults seeded from gestures.json (tones inferred from keys) or a standard tone set
default_catalogs = {
    "tones": list(gestures_map.keys()) or ["calm", "assertive", "motivational", "relaxed", "angry"],
    "gestures": gestures_map or {
        "calm": [],
        "assertive": [],
        "motivational": [],
        "relaxed": [],
        "angry": [],
    },
}
catalogs = _load_json_or(default_catalogs, catalogs_fp)

default_statements = {
    "PreMatch": {tone: [] for tone in catalogs.get("tones", [])},
    "HalfTime": {sc.value: {tone: [] for tone in catalogs.get("tones", [])} for sc in ScoreState},
    "FullTime": {sc.value: {tone: [] for tone in catalogs.get("tones", [])} for sc in ScoreState},
}
statements = _load_json_or(default_statements, statements_fp)

# Mapping: which statements are allowed for each gesture at each stage/score per tone.
# Stored as indices into the statements lists so it remains stable if texts are edited.
default_gesture_statements = {
    "PreMatch": {},
    "HalfTime": {sc.value: {} for sc in ScoreState},
    "FullTime": {sc.value: {} for sc in ScoreState},
}
gesture_statements = _load_json_or(default_gesture_statements, gesture_statements_fp)

tab_g, tab_s = st.tabs(["Gestures", "Statements"])

with tab_g:
    st.markdown("#### Gestures")
    st.info("📝 **Instructions:** Enter one item per line. Each line becomes a separate gesture or tone.")
    
    tones = st.text_area("Tones (one per line)", 
                        value="\n".join(catalogs.get("tones", [])),
                        help="Define the different emotional tones available (e.g., calm, assertive, motivational)")
    
    st.markdown("##### Gestures by tone")
    st.caption("💡 Add one gesture per line for each tone. These are the physical actions/expressions your manager can make.")
    
    new_gestures_map = {}
    tone_list = [ln.strip() for ln in tones.splitlines() if ln.strip()] or catalogs.get("tones", [])
    for tone in tone_list:
        default_lines = catalogs.get("gestures", {}).get(tone, [])
        txt = st.text_area(f"{tone} gestures", 
                          value="\n".join(default_lines),
                          help=f"Enter {tone} gestures, one per line (e.g., 'Nod approvingly', 'Point to the pitch')")
        new_gestures_map[tone] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if st.button("Save gestures"):
        try:
            catalogs.update({
                "tones": tone_list,
                "gestures": new_gestures_map,
            })
            catalogs_fp.write_text(json.dumps(catalogs, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Gestures saved")
        except Exception as e:
            st.error(f"Failed to save gestures: {e}")

with tab_s:
    st.markdown("#### Statements")
    tones_list = catalogs.get("tones", [])
    
    # Initialize all sections
    new_pm = {}
    new_ht = {}
    new_ft = {}
    
    # PreMatch Section
    with st.expander("🎯 PreMatch Statements", expanded=False):
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says before the match starts, organized by gesture.")
        st.markdown("##### PreMatch by gesture")
        gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
        all_gestures = ["No Gesture"] + [g for g in gestures_all if g != "No Gesture"]
        for i, gesture in enumerate(all_gestures):
            txt = st.text_area(f"PreMatch • {gesture}", 
                              value="\n".join(statements.get("PreMatch", {}).get(gesture, [])), 
                              key=f"pm_gesture_{i}_{gesture.replace(' ', '_').replace('-', '_')}",
                              help=f"Enter statements available when using '{gesture}' gesture, one per line")
            new_pm[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        
        if st.button("Save PreMatch", key="save_pm"):
            try:
                statements["PreMatch"] = new_pm
                statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("PreMatch statements saved")
            except Exception as e:
                st.error(f"Failed to save PreMatch statements: {e}")
    
    # HalfTime Section
    with st.expander("⏰ HalfTime Statements", expanded=False):
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says at half-time based on score situation and gesture.")
        st.markdown("##### HalfTime by score and gesture")
        gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
        all_gestures = ["No Gesture"] + [g for g in gestures_all if g != "No Gesture"]
        for sc in [s.value for s in ScoreState]:
            st.markdown(f"**{sc}**")
            row = {}
            for i, gesture in enumerate(all_gestures):
                key = f"HT • {sc} • {gesture}"
                txt = st.text_area(key, 
                                  value="\n".join(((statements.get("HalfTime", {}).get(sc, {}) or {}).get(gesture, []))), 
                                  key=f"ht_{sc}_gesture_{i}_{gesture.replace(' ', '_').replace('-', '_')}",
                                  help=f"Enter statements available when {sc.lower()} and using '{gesture}' gesture, one per line")
                row[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            new_ht[sc] = row
        
        if st.button("Save HalfTime", key="save_ht"):
            try:
                statements["HalfTime"] = new_ht
                statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("HalfTime statements saved")
            except Exception as e:
                st.error(f"Failed to save HalfTime statements: {e}")
    
    # FullTime Section
    with st.expander("🏁 FullTime Statements", expanded=False):
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says after the match based on final result and gesture.")
        st.markdown("##### FullTime by score and gesture")
        gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
        all_gestures = ["No Gesture"] + [g for g in gestures_all if g != "No Gesture"]
        for sc in [s.value for s in ScoreState]:
            st.markdown(f"**{sc}**")
            row = {}
            for i, gesture in enumerate(all_gestures):
                key = f"FT • {sc} • {gesture}"
                txt = st.text_area(key, 
                                  value="\n".join(((statements.get("FullTime", {}).get(sc, {}) or {}).get(gesture, []))), 
                                  key=f"ft_{sc}_gesture_{i}_{gesture.replace(' ', '_').replace('-', '_')}",
                                  help=f"Enter statements available after {sc.lower()} and using '{gesture}' gesture, one per line")
                row[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            new_ft[sc] = row
        
        if st.button("Save FullTime", key="save_ft"):
            try:
                statements["FullTime"] = new_ft
                statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("FullTime statements saved")
            except Exception as e:
                st.error(f"Failed to save FullTime statements: {e}")
    
    # Save All Button
    st.divider()
    if st.button("💾 Save All Statements", key="save_all"):
        try:
            statements["PreMatch"] = new_pm
            statements["HalfTime"] = new_ht
            statements["FullTime"] = new_ft
            statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("All statements saved")
        except Exception as e:
            st.error(f"Failed to save statements: {e}")



st.divider()

# Import/Export Section
col1, col2 = st.columns(2)

with col1:
    with st.expander("📥 Import JSON Files", expanded=False):
        st.info("🔄 **Instructions:** Upload JSON files to replace the current data. Make sure the JSON structure matches the exported format.")
        
        # Import Gestures/Catalogs
        uploaded_catalogs = st.file_uploader("Import Gestures & Tones (catalogs.json)", type="json", key="import_catalogs")
        if uploaded_catalogs and st.button("Import Gestures", key="btn_import_catalogs"):
            try:
                imported_data = json.loads(uploaded_catalogs.read().decode('utf-8'))
                catalogs_fp.write_text(json.dumps(imported_data, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Gestures & Tones imported successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import gestures: {e}")
        
        # Import Statements
        uploaded_statements = st.file_uploader("Import Statements (statements.json)", type="json", key="import_statements")
        if uploaded_statements and st.button("Import Statements", key="btn_import_statements"):
            try:
                imported_data = json.loads(uploaded_statements.read().decode('utf-8'))
                statements_fp.write_text(json.dumps(imported_data, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Statements imported successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import statements: {e}")
        
        # Import Links
        uploaded_links = st.file_uploader("Import Gesture-Statement Links (gesture_statements.json)", type="json", key="import_links")
        if uploaded_links and st.button("Import Links", key="btn_import_links"):
            try:
                imported_data = json.loads(uploaded_links.read().decode('utf-8'))
                gesture_statements_fp.write_text(json.dumps(imported_data, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Gesture-Statement Links imported successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import links: {e}")

with col2:
    with st.expander("📤 Export JSON Files", expanded=False):
        st.info("💾 **Instructions:** Download your current data as JSON files. You can edit these externally and re-import them.")
        
        try:
            st.download_button(
                "📋 Download Gestures & Tones (catalogs.json)", 
                data=catalogs_fp.read_text(encoding="utf-8"), 
                file_name="catalogs.json", 
                mime="application/json",
                help="Contains all tones and their associated gestures"
            )
        except Exception:
            st.info("No catalogs.json yet - save gestures first")
        
        try:
            st.download_button(
                "💬 Download Statements (statements.json)", 
                data=statements_fp.read_text(encoding="utf-8"), 
                file_name="statements.json", 
                mime="application/json",
                help="Contains all statements organized by match stage, score state, and tone"
            )
        except Exception:
            st.info("No statements.json yet - save statements first")
        
        try:
            st.download_button(
                "🔗 Download Links (gesture_statements.json)", 
                data=gesture_statements_fp.read_text(encoding="utf-8"), 
                file_name="gesture_statements.json", 
                mime="application/json",
                help="Contains which statements are available for each gesture"
            )
        except Exception:
            st.info("No gesture_statements.json yet - configure links first")

# JSON Preview Section
with st.expander("👀 Preview Current JSON Structure", expanded=False):
    st.info("🔍 **Preview:** See the current JSON structure of your data before exporting.")
    
    preview_tab1, preview_tab2, preview_tab3 = st.tabs(["Gestures/Tones", "Statements", "Links"])
    
    with preview_tab1:
        st.json(catalogs, expanded=False)
    
    with preview_tab2:
        st.json(statements, expanded=False)
    
    with preview_tab3:
        st.json(gesture_statements, expanded=False)
    
