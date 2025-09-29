import json
import streamlit as st
from pathlib import Path

from services.repository import Repository
from domain.models import (
    MatchStage, ScoreState, FavStatus, Venue, Context
)
from domain.rules_engine import detect_fav_status, detect_matchup_tier, recommend
from domain.ml_assist import load_model, extract_features, to_vector_row, predict_proba

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

tab_g, tab_s, tab_sh, tab_cfg = st.tabs(["Gestures", "Statements", "Shouts", "Engine Config"])

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

with tab_cfg:
    st.markdown("#### Engine Scoring & Detection")
    st.caption("Tune favourite detection and the tiered advantage model. Changes save to engine_config.json.")
    cfg_fp = norm_dir / "engine_config.json"
    try:
        cfg = json.loads(cfg_fp.read_text(encoding="utf-8")) if cfg_fp.exists() else {}
    except Exception:
        cfg = {}
    fav_cfg = cfg.get("favourite_detection", {})
    adv_cfg = cfg.get("advantage_model", {})
    ml_cfg = cfg.get("ml_assist", {})

    # Small model status badge
    try:
        _mod_dir = Path(ml_cfg.get("model_dir", "data/ml"))
        _g_ok = (_mod_dir / "gesture.joblib").exists()
        _s_ok = (_mod_dir / "shout.joblib").exists()
        badge = f"Models: gesture {'✅' if _g_ok else '❌'}, shout {'✅' if _s_ok else '❌'} (dir: {_mod_dir})"
        st.caption(badge)
    except Exception:
        pass

    edit_cfg = st.checkbox("Enable editing (advanced)", value=False, key="edit_cfg")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Favourite detection**")
        pos_gap_threshold = st.number_input("Position gap threshold", 1, 12, int(fav_cfg.get("pos_gap_threshold", 3)), disabled=not edit_cfg)
        pos_weight = st.number_input("Position weight", 0, 5, int(fav_cfg.get("pos_weight", 1)), disabled=not edit_cfg)
        form_diff_threshold = st.number_input("Form diff threshold", 0, 10, int(fav_cfg.get("form_diff_threshold", 2)), disabled=not edit_cfg)
        form_weight = st.number_input("Form weight", 0, 5, int(fav_cfg.get("form_weight", 1)), disabled=not edit_cfg)
        home_bonus = st.number_input("Home bonus", 0, 5, int(fav_cfg.get("home_bonus", 1)), disabled=not edit_cfg)
        away_penalty = st.number_input("Away penalty", 0, 5, int(fav_cfg.get("away_penalty", 1)), disabled=not edit_cfg)
        favourite_threshold = st.number_input("Favourite score threshold", -10, 10, int(fav_cfg.get("favourite_threshold", 2)), disabled=not edit_cfg)
        st.markdown("Special away rules")
        specials = fav_cfg.get("special_rules", {}) or {}
        require_both = st.checkbox("Require BOTH pos and form to be favourite away", value=bool(specials.get("require_both_pos_and_form_to_be_favourite_away", False)), disabled=not edit_cfg)
        never_fav_away_ge = st.number_input("Never favourite away if worse by ≥", 0, 12, int(specials.get("never_favourite_away_if_pos_gap_disadvantage_ge", 0)), disabled=not edit_cfg)
    with col_b:
        st.markdown("**Advantage model (tiering)**")
        pos_w = st.number_input("pos_weight", 0.0, 5.0, float(adv_cfg.get("pos_weight", 1.0)), 0.1, disabled=not edit_cfg)
        form_w = st.number_input("form_weight", 0.0, 5.0, float(adv_cfg.get("form_weight", 0.8)), 0.1, disabled=not edit_cfg)
        home_w = st.number_input("venue_home", -2.0, 2.0, float(adv_cfg.get("venue_home", 0.6)), 0.1, disabled=not edit_cfg)
        away_w = st.number_input("venue_away", -2.0, 2.0, float(adv_cfg.get("venue_away", -0.6)), 0.1, disabled=not edit_cfg)
        xg_w = st.number_input("xg_weight", 0.0, 5.0, float(adv_cfg.get("xg_weight", 0.8)), 0.1, disabled=not edit_cfg)
        shots_w = st.number_input("shots_weight", 0.0, 5.0, float(adv_cfg.get("shots_weight", 0.4)), 0.1, disabled=not edit_cfg)
        poss_w = st.number_input("possession_weight", 0.0, 5.0, float(adv_cfg.get("possession_weight", 0.3)), 0.1, disabled=not edit_cfg)
        cap = st.number_input("cap", 0.0, 20.0, float(adv_cfg.get("cap", 5.0)), 0.5, disabled=not edit_cfg)
        tiers = adv_cfg.get("tiers", {}) or {}
        st.markdown("Thresholds → tiers")
        strong_fav = st.number_input("strong_fav (≥)", -10.0, 10.0, float(tiers.get("strong_fav", 2.5)), 0.1, disabled=not edit_cfg)
        slight_fav = st.number_input("slight_fav (≥)", -10.0, 10.0, float(tiers.get("slight_fav", 0.8)), 0.1, disabled=not edit_cfg)
        even_hi = st.number_input("even_hi (<)", -10.0, 10.0, float(tiers.get("even_hi", 0.8)), 0.1, disabled=not edit_cfg)
        even_lo = st.number_input("even_lo (>)", -10.0, 10.0, float(tiers.get("even_lo", -0.8)), 0.1, disabled=not edit_cfg)
        slight_dog = st.number_input("slight_dog (≤)", -10.0, 10.0, float(tiers.get("slight_dog", -0.8)), 0.1, disabled=not edit_cfg)
        strong_dog = st.number_input("strong_dog (≤)", -10.0, 10.0, float(tiers.get("strong_dog", -2.5)), 0.1, disabled=not edit_cfg)

    st.markdown("**ML assist (logging + inference)**")
    col_ml1, col_ml2 = st.columns([1,3])
    with col_ml1:
        ml_log = st.checkbox("Log features for offline ML", value=bool(ml_cfg.get("log_features", False)), disabled=not edit_cfg)
    with col_ml2:
        ml_path = st.text_input("CSV path", value=str(ml_cfg.get("path", "data/logs/ml/features.csv")), disabled=not edit_cfg, help="Relative to project root")
    col_ml3, col_ml4, col_ml5 = st.columns([1,2,1])
    with col_ml3:
        ml_inf = st.checkbox("Enable inference (re-rank)", value=bool(ml_cfg.get("inference_enabled", False)), disabled=not edit_cfg)
    with col_ml4:
        ml_model_dir = st.text_input("Model directory", value=str(ml_cfg.get("model_dir", "data/ml")), disabled=not edit_cfg)
    with col_ml5:
        ml_weight = st.number_input("Weight", 0.0, 1.0, float(ml_cfg.get("weight", 0.25)), 0.05, disabled=not edit_cfg, help="Higher = stronger application of ML suggestion")

    # Per-stage toggles
    st.caption("Per-stage inference (use sparingly on talk stages)")
    stages_cfg = ml_cfg.get("stages", {}) or {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stg_pm = st.checkbox("PreMatch", value=bool(stages_cfg.get("PreMatch", False)), disabled=not edit_cfg)
    with c2:
        stg_ht = st.checkbox("HalfTime", value=bool(stages_cfg.get("HalfTime", True)), disabled=not edit_cfg)
    with c3:
        stg_ft = st.checkbox("FullTime", value=bool(stages_cfg.get("FullTime", False)), disabled=not edit_cfg)
    with c4:
        stg_el = st.checkbox("Early", value=bool(stages_cfg.get("Early", True)), disabled=not edit_cfg)
    c5, c6, c7 = st.columns(3)
    with c5:
        stg_md = st.checkbox("Mid", value=bool(stages_cfg.get("Mid", True)), disabled=not edit_cfg)
    with c6:
        stg_lt = st.checkbox("Late", value=bool(stages_cfg.get("Late", True)), disabled=not edit_cfg)
    with c7:
        stg_vl = st.checkbox("VeryLate", value=bool(stages_cfg.get("VeryLate", True)), disabled=not edit_cfg)

    if st.button("💾 Save Engine Config", disabled=not edit_cfg):
        try:
            cfg_new = {
                "favourite_detection": {
                    "pos_gap_threshold": int(pos_gap_threshold),
                    "pos_weight": int(pos_weight),
                    "form_diff_threshold": int(form_diff_threshold),
                    "form_weight": int(form_weight),
                    "home_bonus": int(home_bonus),
                    "away_penalty": int(away_penalty),
                    "favourite_threshold": int(favourite_threshold),
                    "special_rules": {
                        "require_both_pos_and_form_to_be_favourite_away": bool(require_both),
                        "never_favourite_away_if_pos_gap_disadvantage_ge": int(never_fav_away_ge)
                    }
                },
                "advantage_model": {
                    "pos_weight": float(pos_w),
                    "form_weight": float(form_w),
                    "venue_home": float(home_w),
                    "venue_away": float(away_w),
                    "xg_weight": float(xg_w),
                    "shots_weight": float(shots_w),
                    "possession_weight": float(poss_w),
                    "cap": float(cap),
                    "tiers": {
                        "strong_fav": float(strong_fav),
                        "slight_fav": float(slight_fav),
                        "even_hi": float(even_hi),
                        "even_lo": float(even_lo),
                        "slight_dog": float(slight_dog),
                        "strong_dog": float(strong_dog)
                    }
                },
                "ml_assist": {
                    "log_features": bool(ml_log),
                    "path": ml_path or "data/logs/ml/features.csv",
                    "inference_enabled": bool(ml_inf),
                    "model_dir": ml_model_dir or "data/ml",
                    "weight": float(ml_weight),
                    "stages": {
                        "PreMatch": bool(stg_pm),
                        "HalfTime": bool(stg_ht),
                        "FullTime": bool(stg_ft),
                        "Early": bool(stg_el),
                        "Mid": bool(stg_md),
                        "Late": bool(stg_lt),
                        "VeryLate": bool(stg_vl),
                    },
                }
            }
            cfg_fp.write_text(json.dumps(cfg_new, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Engine config saved")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save engine config: {e}")

    st.markdown("---")
    with st.expander("🤖 ML Model Status & Quick Validation", expanded=False):
        mod_dir = Path(ml_cfg.get("model_dir", "data/ml"))
        g_ok = (mod_dir / "gesture.joblib").exists()
        s_ok = (mod_dir / "shout.joblib").exists()
        st.write({"gesture_model": g_ok, "shout_model": s_ok, "dir": str(mod_dir)})

        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            vv = st.selectbox("Venue", ["Home","Away"], index=0, key="mlv")
            stg = st.selectbox("Stage", [s.value for s in MatchStage], index=0, key="mls")
        with pc2:
            fav_auto = st.checkbox("Auto fav", value=True, key="mlauto")
            fav_sel = st.selectbox("If manual: status", [f.value for f in FavStatus], index=0, disabled=fav_auto, key="mlfav")
        with pc3:
            sc = st.selectbox("Score", [s.value for s in ScoreState], index=1, key="mlsc")
        tpos, opos = st.columns(2)
        with tpos:
            tp = st.number_input("Your pos", 1, 24, 7, key="mltp")
        with opos:
            op = st.number_input("Opp pos", 1, 24, 12, key="mlop")
        tf, of = st.columns(2)
        with tf:
            tform = st.text_input("Your form", value="WWDLW", key="mltf")
        with of:
            oform = st.text_input("Opp form", value="LDLLD", key="mlof")

        if st.button("Run ML validation", key="ml_run_val"):
            ctx = Context(
                stage=MatchStage(stg),
                fav_status=FavStatus.FAVOURITE if (fav_sel=="Favourite") else FavStatus.UNDERDOG,
                venue=Venue(vv),
                score_state=ScoreState(sc),
                team_position=int(tp), opponent_position=int(op),
                team_form=tform, opponent_form=oform,
                auto_fav_status=bool(fav_auto),
            )
            if fav_auto:
                try:
                    fav, fav_expl = detect_fav_status(ctx)
                    ctx.fav_status = fav
                    st.caption(f"Auto fav: {fav.value} — {fav_expl}")
                except Exception as e:
                    st.warning(f"Fav detect failed: {e}")
            try:
                tier, edge, _ = detect_matchup_tier(ctx)
            except Exception:
                tier, edge = None, None
            rec = recommend(ctx)
            st.write({
                "rules": {"gesture": rec.gesture, "shout": getattr(rec.shout, 'value', str(rec.shout))},
                "tier": getattr(tier, 'value', None),
                "edge": edge,
            })
            # ML probs (if models exist)
            feats = extract_features(ctx, getattr(tier, 'value', None), edge)
            vec = to_vector_row(feats)
            gmod = load_model(mod_dir, "gesture")
            smod = load_model(mod_dir, "shout")
            gprobs = predict_proba(gmod, vec) if gmod else None
            sprobs = predict_proba(smod, vec) if smod else None
            st.json({"gesture_proba": gprobs or {}, "shout_proba": sprobs or {}})
    st.markdown("##### Preview detection (uses saved config)")
    colp, colq, colr = st.columns(3)
    with colp:
        venue = st.selectbox("Venue", ["Home","Away"], index=0)
        team_pos = st.number_input("Your position", 1, 24, 6)
        opp_pos = st.number_input("Opp position", 1, 24, 12)
    with colq:
        team_form = st.text_input("Your form (5 chars W/D/L)", value="WWDLW")
        opp_form = st.text_input("Opp form (5 chars W/D/L)", value="LDLLD")
    with colr:
        xg_for = st.number_input("xG For", 0.0, 10.0, 0.0, 0.05)
        xg_against = st.number_input("xG Against", 0.0, 10.0, 0.0, 0.05)
        possession = st.number_input("Possession %", 0, 100, 50)

    sample_ctx = Context(
        stage=MatchStage.PRE_MATCH,
        fav_status=FavStatus.FAVOURITE,
        venue=Venue(venue),
        team_position=int(team_pos), opponent_position=int(opp_pos),
        team_form=team_form, opponent_form=opp_form,
        xg_for=float(xg_for), xg_against=float(xg_against),
        possession_pct=float(possession),
        auto_fav_status=True,
    )
    try:
        fav, fav_expl = detect_fav_status(sample_ctx)
        st.info(f"Favourite detection: {fav.value} — {fav_expl}")
    except Exception as e:
        st.warning(f"Favourite detection failed: {e}")
    try:
        tier, edge, tex = detect_matchup_tier(sample_ctx)
        st.caption(f"Tier: {tier.value} • Edge: {edge:.2f}")
        with st.expander("Tier explanation"):
            st.write(tex)
    except Exception as e:
        st.warning(f"Tier calc failed: {e}")

    st.markdown("---")
    with st.expander("🔎 Rule hit preview (sample context)", expanded=False):
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            p_stage = st.selectbox("Stage", [s.value for s in MatchStage if s in (MatchStage.PRE_MATCH, MatchStage.EARLY, MatchStage.MID, MatchStage.LATE, MatchStage.VERY_LATE, MatchStage.HALF_TIME, MatchStage.FULL_TIME)], index=0)
        with pc2:
            p_venue = st.selectbox("Venue", ["Home","Away"], index=0, key="prev_venue")
        with pc3:
            p_auto = st.checkbox("Auto-detect favourite", value=True, key="prev_auto")
        with pc4:
            p_fav = st.selectbox("Status", ["Favourite","Underdog"], index=0, disabled=p_auto, key="prev_fav")

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            p_score = st.selectbox("Score state", ["Drawing","Winning","Losing"], index=0)
        with sc2:
            p_team_pos = st.number_input("Your pos", 1, 24, 7, key="prev_tpos")
        with sc3:
            p_opp_pos = st.number_input("Opp pos", 1, 24, 5, key="prev_opos")

        sf1, sf2 = st.columns(2)
        with sf1:
            p_team_form = st.text_input("Your form", value="WWDLW", key="prev_tform")
        with sf2:
            p_opp_form = st.text_input("Opp form", value="LDLLD", key="prev_oform")

        if st.button("Run preview", key="run_rule_preview"):
            ctx = Context(
                stage=MatchStage(p_stage),
                fav_status=FavStatus.FAVOURITE if p_fav == "Favourite" else FavStatus.UNDERDOG,
                venue=Venue(p_venue),
                score_state=ScoreState(p_score),
                team_position=int(p_team_pos), opponent_position=int(p_opp_pos),
                team_form=p_team_form, opponent_form=p_opp_form,
                auto_fav_status=bool(p_auto),
            )
            try:
                if p_auto:
                    fav, fav_expl = detect_fav_status(ctx)
                    ctx.fav_status = fav
                    st.info(f"Auto status: {fav.value} — {fav_expl}")
                tier, edge, tex = detect_matchup_tier(ctx)
                st.caption(f"Tier: {tier.value} • Edge: {edge:.2f}")
                rec = recommend(ctx)
                if rec is None:
                    st.warning("No base rule matched.")
                else:
                    st.success("Rule matched and recommendation built.")
                    st.write({
                        "mentality": rec.mentality.value,
                        "gesture": rec.gesture,
                        "shout": rec.shout.value if hasattr(rec.shout, 'value') else str(rec.shout),
                        "team_talk": rec.team_talk,
                    })
                    if getattr(rec, "trace", None):
                        st.code("\n".join(rec.trace[:5]), language="text")
            except Exception as e:
                st.error(f"Preview failed: {e}")

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
    
