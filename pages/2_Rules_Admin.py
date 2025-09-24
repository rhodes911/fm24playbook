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

tab_g, tab_s, tab_l = st.tabs(["Gestures", "Statements", "Links (Gesture → Statements)"])

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
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says before the match starts.")
        st.markdown("##### PreMatch by tone")
        for t in tones_list:
            txt = st.text_area(f"PreMatch • {t}", 
                              value="\n".join(statements.get("PreMatch", {}).get(t, [])), 
                              key=f"pm_{t}",
                              help=f"Enter {t} pre-match statements, one per line (e.g., 'Let's show them what we're made of!')")
            new_pm[t] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        
        if st.button("Save PreMatch", key="save_pm"):
            try:
                statements["PreMatch"] = new_pm
                statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("PreMatch statements saved")
            except Exception as e:
                st.error(f"Failed to save PreMatch statements: {e}")
    
    # HalfTime Section
    with st.expander("⏰ HalfTime Statements", expanded=False):
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says at half-time based on the current score situation.")
        st.markdown("##### HalfTime by score and tone")
        for sc in [s.value for s in ScoreState]:
            st.markdown(f"**{sc}**")
            row = {}
            for t in tones_list:
                key = f"HT • {sc} • {t}"
                txt = st.text_area(key, 
                                  value="\n".join(((statements.get("HalfTime", {}).get(sc, {}) or {}).get(t, []))), 
                                  key=f"ht_{sc}_{t}",
                                  help=f"Enter {t} half-time statements when {sc.lower()}, one per line")
                row[t] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
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
        st.info("📝 **Instructions:** Enter one statement per line. These are things your manager says after the match based on the final result.")
        st.markdown("##### FullTime by score and tone")
        for sc in [s.value for s in ScoreState]:
            st.markdown(f"**{sc}**")
            row = {}
            for t in tones_list:
                key = f"FT • {sc} • {t}"
                txt = st.text_area(key, 
                                  value="\n".join(((statements.get("FullTime", {}).get(sc, {}) or {}).get(t, []))), 
                                  key=f"ft_{sc}_{t}",
                                  help=f"Enter {t} full-time statements after {sc.lower()}, one per line")
                row[t] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
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

with tab_l:
    st.markdown("#### Configure Statement Availability for Gestures")
    st.info("🔗 **Instructions:** Configure which statements remain available (white) vs greyed out when each gesture is selected. This mirrors the FM24 behavior you see in-game.")
    
    # Quick setup section
    with st.expander("⚡ Quick Setup - Apply Gesture to Multiple Statements", expanded=True):
        st.markdown("**Batch assign a gesture to multiple statements at once**")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            quick_stage = st.selectbox("Stage", options=[MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME], format_func=lambda x: x.value, key="quick_stage")
        with col2:
            quick_score = None
            if quick_stage in (MatchStage.HALF_TIME, MatchStage.FULL_TIME):
                quick_score = st.selectbox("Score", options=[ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING], format_func=lambda x: x.value, key="quick_score")
        with col3:
            gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
            quick_gesture = st.selectbox("Gesture to Apply", options=["No Gesture"] + gestures_all, key="quick_gesture")
        
        if quick_gesture != "No Gesture":
            st.markdown(f"**Statements available when '{quick_gesture}' is selected:**")
            
            # Get statements for this stage/score
            tones_list = catalogs.get("tones", [])
            for tone in tones_list:
                if quick_stage == MatchStage.PRE_MATCH:
                    tone_statements = statements.get("PreMatch", {}).get(tone, [])
                else:
                    key = "HalfTime" if quick_stage == MatchStage.HALF_TIME else "FullTime"
                    tone_statements = ((statements.get(key, {}).get(quick_score.value, {}) or {}).get(tone, []))
                
                if tone_statements:
                    st.markdown(f"**{tone.upper()} Statements:**")
                    
                    # Get current settings
                    def _quick_node():
                        if quick_stage == MatchStage.PRE_MATCH:
                            gs = gesture_statements.setdefault("PreMatch", {})
                            return gs.setdefault(quick_gesture, {})
                        key = "HalfTime" if quick_stage == MatchStage.HALF_TIME else "FullTime"
                        gs = gesture_statements.setdefault(key, {})
                        gs = gs.setdefault(quick_score.value, {})
                        return gs.setdefault(quick_gesture, {})
                    
                    quick_node = _quick_node()
                    allowed_idx = set(quick_node.get(tone, []))
                    
                    # Create columns for better layout
                    cols = st.columns(2)
                    new_allowed = []
                    
                    for i, stmt in enumerate(tone_statements):
                        col_idx = i % 2
                        with cols[col_idx]:
                            checked = st.checkbox(
                                stmt[:80] + "..." if len(stmt) > 80 else stmt, 
                                value=(i in allowed_idx), 
                                key=f"quick_{quick_stage.value}_{quick_score.value if quick_score else 'NA'}_{quick_gesture}_{tone}_{i}"
                            )
                            if checked:
                                new_allowed.append(i)
                    
                    quick_node[tone] = new_allowed
            
            col_save, col_clear = st.columns(2)
            with col_save:
                if st.button("💾 Save Configuration", key="save_quick"):
                    try:
                        gesture_statements_fp.write_text(json.dumps(gesture_statements, indent=2, ensure_ascii=False), encoding="utf-8")
                        st.success(f"Saved configuration for '{quick_gesture}'!")
                    except Exception as e:
                        st.error(f"Failed to save: {e}")
            
            with col_clear:
                if st.button("🗑️ Clear All for this Gesture", key="clear_quick"):
                    try:
                        quick_node = _quick_node()
                        for tone in tones_list:
                            quick_node[tone] = []
                        gesture_statements_fp.write_text(json.dumps(gesture_statements, indent=2, ensure_ascii=False), encoding="utf-8")
                        st.success(f"Cleared all statements for '{quick_gesture}'!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to clear: {e}")
    
    # Original detailed section
    with st.expander("🔧 Advanced - Individual Statement Configuration", expanded=False):
        st.caption("Fine-tune individual statement availability per gesture")
        
        stg = st.selectbox("Stage", options=[MatchStage.PRE_MATCH, MatchStage.HALF_TIME, MatchStage.FULL_TIME], format_func=lambda x: x.value, key="adv_stage")
        sel_score = None
        if stg in (MatchStage.HALF_TIME, MatchStage.FULL_TIME):
            sel_score = st.selectbox("Score state", options=[ScoreState.WINNING, ScoreState.DRAWING, ScoreState.LOSING], format_func=lambda x: x.value, key="adv_score")
        
        gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
        gest = st.selectbox("Gesture", options=gestures_all, key="adv_gesture")
        
        # Access the mapping node for this selection
        def _node():
            if stg == MatchStage.PRE_MATCH:
                gs = gesture_statements.setdefault("PreMatch", {})
                return gs.setdefault(gest, {})
            key = "HalfTime" if stg == MatchStage.HALF_TIME else "FullTime"
            gs = gesture_statements.setdefault(key, {})
            gs = gs.setdefault(sel_score.value, {})
            return gs.setdefault(gest, {})

        node = _node()
        tones_list = catalogs.get("tones", [])
        
        for t in tones_list:
            st.markdown(f"**{t}**")
            if stg == MatchStage.PRE_MATCH:
                items = statements.get("PreMatch", {}).get(t, [])
            else:
                key = "HalfTime" if stg == MatchStage.HALF_TIME else "FullTime"
                items = ((statements.get(key, {}).get(sel_score.value, {}) or {}).get(t, []))
            
            allowed_idx = set(node.get(t, []))
            new_allowed = []
            for i, text in enumerate(items):
                checked = st.checkbox(text or f"[{t}] #{i}", value=(i in allowed_idx), key=f"adv_{stg.value}_{sel_score.value if sel_score else 'NA'}_{gest}_{t}_{i}")
                if checked:
                    new_allowed.append(i)
            node[t] = new_allowed
        
        if st.button("Save Advanced Configuration", key="save_adv"):
            try:
                gesture_statements_fp.write_text(json.dumps(gesture_statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Advanced configuration saved")
            except Exception as e:
                st.error(f"Failed to save: {e}")
    
    # Overview section
    with st.expander("📊 Overview - Current Configuration", expanded=False):
        st.markdown("##### Configuration Matrix (PreMatch)")
        try:
            pm = gesture_statements.get("PreMatch", {})
            tones_list = catalogs.get("tones", [])
            gestures_all = sorted({g for arr in catalogs.get("gestures", {}).values() for g in arr})
            
            rows = []
            for g in gestures_all:
                row = {"Gesture": g}
                total = 0
                for t in tones_list:
                    count = len((pm.get(g, {}) or {}).get(t, []))
                    row[t] = count
                    total += count
                row["Total"] = total
                rows.append(row)
            
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
                
                # Summary stats
                total_configured = sum(row["Total"] for row in rows)
                st.metric("Total Configured Links", total_configured)
        except Exception as e:
            st.error(f"Failed to generate overview: {e}")

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
    
