import json
import streamlit as st
from pathlib import Path

from services.repository import Repository
from domain.models import (
    MatchStage, ScoreState,
)

st.title("🧱 Rules Admin — Minimal Tables")
st.caption("Only the three granular tables: Gestures, Statements, and Gesture↔Statements links.")

st.divider()
repo = Repository()
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
shouts_fp = norm_dir / "shouts.json"
shout_rules_fp = norm_dir / "shout_rules.json"
shouts_fp = norm_dir / "shouts.json"
shout_rules_fp = norm_dir / "shout_rules.json"

def _load_json_or(default: dict, fp: Path) -> dict:
    try:
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return json.loads(json.dumps(default))

# Defaults seeded from gestures.json (tones inferred from keys) or a standard tone set
default_catalogs = {
    "tones": list(gestures_map.keys()) or ["calm", "assertive", "motivational", "relaxed", "aggressive"],
    "gestures": gestures_map or {
        "calm": [],
        "assertive": [],
        "motivational": [],
        "relaxed": [],
        "aggressive": [],
    },
}
catalogs = _load_json_or(default_catalogs, catalogs_fp)

# Load shouts configuration
default_shouts = {
    "available_shouts": ["Encourage", "Demand More", "Focus", "Fire Up", "Praise", "None"],
    "shout_contexts": {},
    "cooldown_rules": {"same_shout_minutes": 8, "max_shouts_per_half": 6},
    "tone_mapping": {}
}
shouts_config = _load_json_or(default_shouts, shouts_fp)

default_shout_rules = {
    "context_rules": {},
    "suppression_rules": {},
    "tone_selection": {}
}
shout_rules = _load_json_or(default_shout_rules, shout_rules_fp)

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

tab_g, tab_s, tab_sh = st.tabs(["Gestures", "Statements", "Shouts"])

with tab_g:
    st.markdown("#### Gestures")
    st.info("📝 **Instructions:** Enter one item per line. Each line becomes a separate gesture or tone.")
    edit_g = st.checkbox("Enable editing (advanced)", value=False, key="edit_g")
    st.warning(
        "Changing tones/gestures can break references in statements and rules. If you rename/remove gestures, update statements and any gesture→statement links to match.",
        icon="⚠️",
    )
    
    tones = st.text_area("Tones (one per line)", 
                        value="\n".join(catalogs.get("tones", [])),
                        help="Define the different emotional tones available (e.g., calm, assertive, motivational)",
                        disabled=not edit_g)
    
    st.markdown("##### Gestures by tone")
    st.caption("💡 Add one gesture per line for each tone. These are the physical actions/expressions your manager can make.")
    
    new_gestures_map = {}
    tone_list = [ln.strip() for ln in tones.splitlines() if ln.strip()] or catalogs.get("tones", [])
    for tone in tone_list:
        default_lines = catalogs.get("gestures", {}).get(tone, [])
        txt = st.text_area(f"{tone} gestures", 
                          value="\n".join(default_lines),
                          help=f"Enter {tone} gestures, one per line (e.g., 'Nod approvingly', 'Point to the pitch')",
                          disabled=not edit_g)
        new_gestures_map[tone] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if st.button("Save gestures", disabled=not edit_g):
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
    edit_s = st.checkbox("Enable editing (advanced)", value=False, key="edit_s")
    st.warning(
        "Editing statements affects the phrases shown in the app. Removing or reordering items can desync any gesture→statement index mappings.",
        icon="⚠️",
    )
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
                              help=f"Enter statements available when using '{gesture}' gesture, one per line",
                              disabled=not edit_s)
            new_pm[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        
        if st.button("Save PreMatch", key="save_pm", disabled=not edit_s):
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
                                  help=f"Enter statements available when {sc.lower()} and using '{gesture}' gesture, one per line",
                                  disabled=not edit_s)
                row[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            new_ht[sc] = row
        
        if st.button("Save HalfTime", key="save_ht", disabled=not edit_s):
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
                                  help=f"Enter statements available after {sc.lower()} and using '{gesture}' gesture, one per line",
                                  disabled=not edit_s)
                row[gesture] = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            new_ft[sc] = row
        
        if st.button("Save FullTime", key="save_ft", disabled=not edit_s):
            try:
                statements["FullTime"] = new_ft
                statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("FullTime statements saved")
            except Exception as e:
                st.error(f"Failed to save FullTime statements: {e}")
    
    # Save All Button
    st.divider()
    if st.button("💾 Save All Statements", key="save_all", disabled=not edit_s):
        try:
            statements["PreMatch"] = new_pm
            statements["HalfTime"] = new_ht
            statements["FullTime"] = new_ft
            statements_fp.write_text(json.dumps(statements, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("All statements saved")
        except Exception as e:
            st.error(f"Failed to save statements: {e}")

with tab_sh:
    st.markdown("#### Shouts (In-Play Touchline Commands)")
    st.info("🎯 **Key Difference:** Shouts are for in-play match action, separate from team talk gestures/statements")
    edit_sh = st.checkbox("Enable editing (advanced)", value=False, key="edit_sh")
    st.warning(
        "Changing shout contexts or rules can lead to unexpected in-play suggestions. Be cautious with cooldowns and suppression rules.",
        icon="⚠️",
    )
    
    # Shout Context Configuration
    with st.expander("🎮 Shout Contexts & Effectiveness", expanded=True):
        st.markdown("##### Configure when each shout works best")
        
        available_shouts = shouts_config.get("available_shouts", ["Encourage", "Demand More", "Focus", "Fire Up", "Praise", "None"])
        
        new_contexts = {}
        for shout in available_shouts:
            if shout == "None":
                continue
                
            st.markdown(f"**{shout}**")
            col1, col2 = st.columns(2)
            
            current_context = shouts_config.get("shout_contexts", {}).get(shout, {})
            
            with col1:
                description = st.text_input(
                    f"Description", 
                    value=current_context.get("description", ""),
                    key=f"shout_desc_{shout.replace(' ', '_')}",
                    help=f"What does {shout} do?",
                    disabled=not edit_sh
                )
                
                best_when = st.text_area(
                    f"Best when (one per line)",
                    value="\n".join(current_context.get("best_when", [])),
                    key=f"shout_best_{shout.replace(' ', '_')}",
                    help=f"Contexts where {shout} works well",
                    disabled=not edit_sh
                )
            
            with col2:
                avoid_when = st.text_area(
                    f"Avoid when (one per line)",
                    value="\n".join(current_context.get("avoid_when", [])),
                    key=f"shout_avoid_{shout.replace(' ', '_')}",
                    help=f"Contexts where {shout} should not be used",
                    disabled=not edit_sh
                )
            
            new_contexts[shout] = {
                "description": description,
                "best_when": [line.strip() for line in best_when.splitlines() if line.strip()],
                "avoid_when": [line.strip() for line in avoid_when.splitlines() if line.strip()]
            }
    
    # Tone Mapping for Shouts
    with st.expander("🎭 Tone → Shout Mapping", expanded=False):
        st.markdown("##### Which shouts work with each tone")
        st.caption("Select which shouts are compatible with each tone. This determines shout selection during matches.")
        
        tones_list = catalogs.get("tones", [])
        new_tone_mapping = {}
        
        for tone in tones_list:
            current_mapping = shouts_config.get("tone_mapping", {}).get(tone, [])
            selected_shouts = st.multiselect(
                f"{tone.title()} tone → Available shouts",
                options=available_shouts,
                default=current_mapping,
                key=f"tone_map_{tone}",
                help=f"Which shouts work well with {tone} tone?",
                disabled=not edit_sh
            )
            new_tone_mapping[tone] = selected_shouts
    
    # Cooldown Rules
    with st.expander("⏰ Cooldown & Usage Rules", expanded=False):
        st.markdown("##### Prevent shout overuse")
        
        col1, col2, col3 = st.columns(3)
        
        current_cooldowns = shouts_config.get("cooldown_rules", {})
        
        with col1:
            same_shout = st.number_input(
                "Same shout cooldown (minutes)",
                min_value=1, max_value=20,
                value=current_cooldowns.get("same_shout_minutes", 8),
                help="Minimum time before repeating the same shout",
                disabled=not edit_sh
            )
        
        with col2:
            max_per_half = st.number_input(
                "Max shouts per half",
                min_value=1, max_value=15, 
                value=current_cooldowns.get("max_shouts_per_half", 6),
                help="Maximum number of shouts allowed per half",
                disabled=not edit_sh
            )
        
        with col3:
            praise_window = st.number_input(
                "Praise window (minutes)",
                min_value=1, max_value=10,
                value=current_cooldowns.get("praise_window_after_positive", 3),
                help="Time window to praise after positive events",
                disabled=not edit_sh
            )
    
    # Suppression Rules
    with st.expander("🚫 Suppression Rules (Safety)", expanded=False):
        st.markdown("##### Automatic restrictions based on match state")
        
        st.markdown("**Yellow Cards Suppression**")
        col1, col2 = st.columns(2)
        
        with col1:
            cards_threshold = st.number_input(
                "Yellow cards threshold",
                min_value=1, max_value=5,
                value=2,
                help="Suppress aggressive shouts when this many yellows",
                disabled=not edit_sh
            )
        
        with col2:
            suppressed_shouts = st.multiselect(
                "Suppress these shouts",
                options=["Fire Up", "Demand More"],
                default=["Fire Up", "Demand More"],
                help="Which shouts to suppress when too many yellows",
                disabled=not edit_sh
            )
        
        st.markdown("**Time-based Suppression**")
        late_game_suppress = st.multiselect(
            "Late game suppression (when winning)",
            options=["Fire Up", "Demand More"],
            default=["Fire Up"],
            help="Suppress these shouts when winning in final 15 minutes",
            disabled=not edit_sh
        )
    
    # Save Button for Shouts
    if st.button("💾 Save Shout Configuration", key="save_shouts", disabled=not edit_sh):
        try:
            # Update shouts config
            new_shouts_config = {
                "available_shouts": available_shouts,
                "shout_contexts": new_contexts,
                "cooldown_rules": {
                    "same_shout_minutes": same_shout,
                    "max_shouts_per_half": max_per_half,
                    "praise_window_after_positive": praise_window
                },
                "tone_mapping": new_tone_mapping
            }
            
            # Update suppression rules
            new_suppression_rules = {
                "cards": {
                    "yellow_cards_threshold": cards_threshold,
                    "suppressed_shouts": suppressed_shouts
                },
                "time": {
                    "late_game_winning": late_game_suppress
                }
            }
            
            # Save both files
            shouts_fp.write_text(json.dumps(new_shouts_config, indent=2, ensure_ascii=False), encoding="utf-8")
            
            current_shout_rules = shout_rules.copy()
            current_shout_rules["suppression_rules"] = new_suppression_rules
            shout_rules_fp.write_text(json.dumps(current_shout_rules, indent=2, ensure_ascii=False), encoding="utf-8")
            
            st.success("Shout configuration saved!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save shout configuration: {e}")

st.divider()# Import/Export Section
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
        
        # Import Shouts
        uploaded_shouts = st.file_uploader("Import Shouts Config (shouts.json)", type="json", key="import_shouts")
        if uploaded_shouts and st.button("Import Shouts", key="btn_import_shouts"):
            try:
                imported_data = json.loads(uploaded_shouts.read().decode('utf-8'))
                shouts_fp.write_text(json.dumps(imported_data, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Shouts configuration imported successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import shouts: {e}")
        
        # Import Shout Rules
        uploaded_shout_rules = st.file_uploader("Import Shout Rules (shout_rules.json)", type="json", key="import_shout_rules")
        if uploaded_shout_rules and st.button("Import Shout Rules", key="btn_import_shout_rules"):
            try:
                imported_data = json.loads(uploaded_shout_rules.read().decode('utf-8'))
                shout_rules_fp.write_text(json.dumps(imported_data, indent=2, ensure_ascii=False), encoding="utf-8")
                st.success("Shout rules imported successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import shout rules: {e}")

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
        
        try:
            st.download_button(
                "🎮 Download Shouts (shouts.json)", 
                data=shouts_fp.read_text(encoding="utf-8"), 
                file_name="shouts.json", 
                mime="application/json",
                help="Contains shout contexts, cooldowns and tone mapping"
            )
        except Exception:
            st.info("No shouts.json yet - configure shouts first")
        
        try:
            st.download_button(
                "⚙️ Download Shout Rules (shout_rules.json)", 
                data=shout_rules_fp.read_text(encoding="utf-8"), 
                file_name="shout_rules.json", 
                mime="application/json",
                help="Contains shout selection and suppression rules"
            )
        except Exception:
            st.info("No shout_rules.json yet - configure shout rules first")

# JSON Preview Section
with st.expander("👀 Preview Current JSON Structure", expanded=False):
    st.info("🔍 **Preview:** See the current JSON structure of your data before exporting.")
    
    preview_tab1, preview_tab2, preview_tab3, preview_tab4, preview_tab5 = st.tabs(["Gestures/Tones", "Statements", "Links", "Shouts", "Shout Rules"])
    
    with preview_tab1:
        st.json(catalogs, expanded=False)
    
    with preview_tab2:
        st.json(statements, expanded=False)
    
    with preview_tab3:
        st.json(gesture_statements, expanded=False)
    
    with preview_tab4:
        st.json(shouts_config, expanded=False)
    
    with preview_tab5:
        st.json(shout_rules, expanded=False)
    
