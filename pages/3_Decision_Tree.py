import json
from pathlib import Path
import streamlit as st
import html
from domain.models import (
    Context,
    MatchStage,
    FavStatus,
    Venue,
    ScoreState,
    SpecialSituation,
    PlayerReaction,
    TalkAudience,
    Shout,
)
from domain.rules_engine import recommend, detect_fav_status, detect_matchup_tier

st.set_page_config(page_title="Rules Decision Tree", page_icon="🌳", layout="wide")
st.title("🌳 Rules Decision Tree")
st.caption("Filter, inspect, and visualize how base rules, specials, and reactions combine.")

# ---------------- UI polish ----------------
st.markdown(
    """
    <style>
    .chip { display:inline-flex; align-items:center; gap:6px; padding:2px 8px; border-radius:999px; border:1px solid #334155; background:#0b1220; color:#e5e7eb; font-size: 11px; }
    .chip.badge { background:#111827; border-color:#374151; }
    .card { padding:12px; border-radius:10px; border:1px solid #334155; background:#0f172a; }
    .muted { color:#94a3b8; }
    .row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
    </style>
    """,
    unsafe_allow_html=True,
)

base_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "base_rules.json"
special_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "special_overrides.json"
reactions_fp = Path(__file__).resolve().parent.parent / "data" / "rules" / "normalized" / "reaction_rules.json"

@st.cache_data(show_spinner=False)
def load_json(fp: Path):
    try:
        if fp.exists():
            return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

base_rules = load_json(base_fp)
specials = load_json(special_fp)
reactions = load_json(reactions_fp)

# ---------------- Filters ----------------
st.sidebar.header("Filters")
stages = ["PreMatch","Early","Mid","Late","VeryLate","HalfTime","FullTime"]
venues = ["Home","Away"]
favs = ["Favourite","Underdog"]
scores = ["Winning","Drawing","Losing"]

sel_stage = st.sidebar.multiselect("Stage", stages, default=[])
sel_venue = st.sidebar.multiselect("Venue", venues, default=[])
sel_fav = st.sidebar.multiselect("Status", favs, default=[])
sel_score = st.sidebar.multiselect("Score", scores, default=[])
text_query = st.sidebar.text_input("Search (gesture / talk / shout)")

show_specials = st.sidebar.checkbox("Show Specials", value=True)
show_reactions = st.sidebar.checkbox("Show Reactions", value=True)

def rule_matches(r: dict) -> bool:
    w = r.get("when", {})
    rec = r.get("recommendation", {})
    if sel_stage and w.get("stage") not in sel_stage:
        return False
    if sel_venue and w.get("venue") and w.get("venue") not in sel_venue:
        return False
    if sel_fav and w.get("favStatus") and w.get("favStatus") not in sel_fav:
        return False
    if sel_score and w.get("scoreState") and w.get("scoreState") not in sel_score:
        return False
    if text_query:
        q = text_query.lower()
        blob = " ".join([
            str(w.get("stage","")), str(w.get("venue","")), str(w.get("favStatus","")), str(w.get("scoreState","")),
            str(rec.get("gesture","")), str(rec.get("teamTalk","")), str(rec.get("shout",""))
        ]).lower()
        if q not in blob:
            return False
    return True

filtered = [r for r in base_rules if rule_matches(r)]

# ---------------- Graphviz builder ----------------
stage_color = {
    "PreMatch": "#2563eb",
    "Early": "#06b6d4",
    "Mid": "#22c55e",
    "Late": "#f59e0b",
    "VeryLate": "#ef4444",
    "HalfTime": "#a855f7",
    "FullTime": "#64748b",
}

def dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\"", "\\\"")

def _record_text(s: str) -> str:
    """Sanitize text for DOT record labels.
    - Replace double quotes
    - Avoid record separators and braces
    - Trim overly long text
    """
    if s is None:
        s = ""
    s = str(s)
    if len(s) > 160:
        s = s[:160] + "…"
    return (
        s.replace("\"", "'")
         .replace("|", "¦")
         .replace("{", "(")
         .replace("}", ")")
    )

def rule_label(r: dict) -> str:
    w = r.get("when", {})
    rec = r.get("recommendation", {})
    stage = _record_text(w.get("stage", "?"))
    fav = _record_text(w.get("favStatus", "*"))
    venue = _record_text(w.get("venue", "*"))
    score = _record_text(w.get("scoreState", "*"))
    gesture = _record_text(rec.get("gesture", "—"))
    shout = _record_text(rec.get("shout", "None"))
    talk = _record_text(rec.get("teamTalk") or "(auto)")
    # Record label: three rows -> head | body | talk
    head = f"{stage} | {fav} | {venue} | {score}"
    body = f"{gesture} | {shout}"
    return f"{{ {{ {head} }} | {{ {body} }} | {{ {talk} }} }}"

def build_dot(rules: list[dict]) -> str:
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        "  graph [bgcolor=\"#0b1220\", pad=0.3];",
        "  node [shape=record, fontsize=10, fontname=Helvetica, color=gray60, fontcolor=white, style=filled, fillcolor=\"#111827\"];",
        "  edge [color=gray50];",
    ]
    # Cluster by stage
    by_stage: dict[str, list[tuple[str, dict]]] = {}
    for i, r in enumerate(rules):
        w = r.get("when", {})
        s = w.get("stage", "Other")
        by_stage.setdefault(s, []).append((f"rule{i}", r))

    for s, items in by_stage.items():
        color = stage_color.get(s, "#334155")
        # Important: quote hex color, otherwise '#' is parsed as a comment in DOT
        lines.append(f"  subgraph cluster_{dot_escape(s)} {{ label=\"{dot_escape(s)}\"; color=\"{color}\"; style=dashed;")
        for node_id, r in items:
            label = rule_label(r)
            fill = color
            # Use a proper record label (quoted string), not an HTML-like label
            lines.append(f"    {node_id} [label=\"{label}\", fillcolor=\"{fill}\", tooltip=\"{dot_escape(s)}\"];")
        lines.append("  }")

    if show_specials and specials:
        lines.append("  subgraph cluster_specials { label=\"Special Overrides\"; style=dashed; color=\"#64748b\"; ")
        for i, s in enumerate(specials[:10]):
            tag = s.get("tag","?")
            lines.append(f"    spec{i} [label=\"{dot_escape(tag)}\", shape=box, fillcolor=\"#0f172a\"];")
        lines.append("  }")

    if show_reactions and reactions:
        lines.append("  subgraph cluster_react { label=\"Reaction Adjustments\"; style=dashed; color=\"#64748b\"; ")
        for i, r in enumerate(reactions[:10]):
            re = r.get("reaction","?")
            lines.append(f"    react{i} [label=\"{dot_escape(re)}\", shape=box, fillcolor=\"#0f172a\"];")
        lines.append("  }")

    # Soft links (for context)
    for i, _ in enumerate(rules[:15]):
        if show_specials and specials:
            lines.append(f"  rule{i} -> spec0 [style=dotted, color=gray50, arrowhead=none];")
        if show_reactions and reactions:
            lines.append(f"  rule{i} -> react0 [style=dotted, color=gray50, arrowhead=none];")

    lines.append("}")
    return "\n".join(lines)

# ---------------- View switcher ----------------
view = st.radio("View", ["Graph", "Cards", "Simulator"], horizontal=True)

if view == "Graph":
    dot = build_dot(filtered)
    col_g, col_l = st.columns([3,1])
    with col_g:
        st.graphviz_chart(dot, use_container_width=True)
    with col_l:
        st.markdown("**Legend**")
        for k, v in stage_color.items():
            st.markdown(f"<span class='chip' style='background:{v}; border-color:{v}'> {k} </span>", unsafe_allow_html=True)
        st.markdown("<div class='muted'>Shaded clusters group rules by stage. Dotted lines indicate possible specials/reaction phases.</div>", unsafe_allow_html=True)
    with st.expander("Show DOT source", expanded=False):
        st.code(dot, language="dot")
elif view == "Cards":
    # Cards view: scrollable, searchable
    st.write(f"Filtered rules: {len(filtered)} / Total: {len(base_rules)}")
    for r in filtered:
        w = r.get("when", {})
        rec = r.get("recommendation", {})
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='row'><span class='chip badge'>{html.escape(w.get('stage','?'))}</span>"
                f"<span class='chip'>{html.escape(w.get('favStatus','*'))}</span>"
                f"<span class='chip'>{html.escape(w.get('venue','*'))}</span>"
                f"<span class='chip'>{html.escape(w.get('scoreState','*'))}</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='row'><span class='chip'>Gesture: {html.escape(rec.get('gesture','—'))}</span>"
                f"<span class='chip'>Shout: {html.escape(rec.get('shout','None'))}</span></div>",
                unsafe_allow_html=True,
            )
            talk = rec.get("teamTalk") or "(auto)"
            st.markdown(f"<div class='muted'>Talk: {html.escape(talk)}</div>", unsafe_allow_html=True)
            with st.expander("Raw JSON"):
                st.json(r)
            st.markdown("</div>", unsafe_allow_html=True)

if view == "Simulator":
    st.subheader("Scenario Simulator")
    st.caption("Build any context (stage, venue, score, stats, specials) and preview the live recommendation.")

    def _norm_form(s: str) -> str:
        return "".join([c for c in (s or "").upper() if c in ("W","D","L")])[:5]

    col_left, col_right = st.columns([2, 1])
    with col_left:
        with st.form("sim_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                stage = st.selectbox("Stage", [s for s in [
                    "PreMatch","Early","Mid","Late","VeryLate","HalfTime","FullTime"
                ]], index=0)
            with c2:
                venue = st.selectbox("Venue", ["Home","Away"], index=0)
            with c3:
                auto_fav = st.checkbox("Auto-detect favourite", value=True)

            c4, c5 = st.columns(2)
            with c4:
                fav = st.selectbox("Status", ["Favourite","Underdog"], index=0, disabled=auto_fav)
            with c5:
                minute = st.number_input("Minute", min_value=0, max_value=120, value=0, step=1)

            c6, c7 = st.columns(2)
            with c6:
                team_pos = st.number_input("Your league position", min_value=1, max_value=24, value=7)
            with c7:
                opp_pos = st.number_input("Opposition league position", min_value=1, max_value=24, value=5)

            c8, c9 = st.columns(2)
            with c8:
                team_form = st.text_input("Your recent form", value="WWDLD")
            with c9:
                opp_form = st.text_input("Opposition recent form", value="LDLLW")

            st.markdown("---")
            s1, s2, s3 = st.columns(3)
            with s1:
                gf = st.number_input("Goals For", min_value=0, max_value=20, value=0)
            with s2:
                ga = st.number_input("Goals Against", min_value=0, max_value=20, value=0)
            with s3:
                possession = st.number_input("Possession %", min_value=0, max_value=100, value=50)

            s4, s5, s6 = st.columns(3)
            with s4:
                sf = st.number_input("Shots For", min_value=0, max_value=50, value=0)
            with s5:
                sa = st.number_input("Shots Against", min_value=0, max_value=50, value=0)
            with s6:
                sof = st.number_input("On Target For", min_value=0, max_value=50, value=0)

            s7, s8 = st.columns(2)
            with s7:
                soa = st.number_input("On Target Against", min_value=0, max_value=50, value=0)
            with s8:
                xg_for = st.number_input("xG For", min_value=0.0, max_value=15.0, value=0.0, step=0.05, format="%.2f")

            s9, s10 = st.columns(2)
            with s9:
                xg_against = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=0.0, step=0.05, format="%.2f")
            with s10:
                ht_delta = st.number_input("HT score delta (optional)", min_value=-10, max_value=10, value=0)

            st.markdown("---")
            sp1, sp2 = st.columns(2)
            with sp1:
                spec_opts = [s.value for s in SpecialSituation if s != SpecialSituation.NONE]
                specials_sel = st.multiselect("Special situations", spec_opts, default=[])
            with sp2:
                react_opts = [r.value for r in PlayerReaction]
                reactions_sel = st.multiselect("Player reactions", react_opts, default=[])

            submitted = st.form_submit_button("Run simulation", type="primary")

        if submitted:
            # Derive score state from goals
            score_state = ScoreState.DRAWING
            if gf > ga:
                score_state = ScoreState.WINNING
            elif gf < ga:
                score_state = ScoreState.LOSING

            ctx = Context(
                stage=MatchStage(stage),
                fav_status=FavStatus.FAVOURITE if fav == "Favourite" else FavStatus.UNDERDOG,
                venue=Venue(venue),
                score_state=score_state,
                minute=int(minute),
                possession_pct=float(possession),
                shots_for=int(sf), shots_against=int(sa),
                shots_on_target_for=int(sof), shots_on_target_against=int(soa),
                xg_for=float(xg_for), xg_against=float(xg_against),
                team_goals=int(gf), opponent_goals=int(ga),
                team_position=int(team_pos), opponent_position=int(opp_pos),
                team_form=_norm_form(team_form), opponent_form=_norm_form(opp_form),
                special_situations=[SpecialSituation(s) for s in specials_sel],
                player_reactions=[PlayerReaction(r) for r in reactions_sel],
                auto_fav_status=bool(auto_fav),
                ht_score_delta=int(ht_delta) if ht_delta is not None else None,
            )
            if auto_fav:
                try:
                    fav_auto, expl = detect_fav_status(ctx)
                    ctx.fav_status = fav_auto
                    st.info(f"Auto-detected status: {fav_auto.value} — {expl}")
                except Exception as e:
                    st.warning(f"Auto-detect failed: {e}")

            # Always compute granular tier for transparency
            try:
                tier, edge, expl2 = detect_matchup_tier(ctx)
                st.caption(f"Tier: {tier.value} • Edge: {edge:.2f}")
                with st.expander("Tier explanation"):
                    st.write(expl2)
            except Exception as e:
                st.caption(f"Tier calc failed: {e}")

            try:
                rec = recommend(ctx)
            except Exception as e:
                rec = None
                st.error(f"Engine error: {e}")

            if rec:
                st.success("Recommendation ready.")
                st.markdown(
                    f"<div class='card'><div class='row'>"
                    f"<span class='chip badge'>{html.escape(ctx.stage.value)}</span>"
                    f"<span class='chip'>{html.escape(ctx.fav_status.value)}</span>"
                    f"<span class='chip'>{html.escape(ctx.venue.value)}</span>"
                    f"<span class='chip'>{html.escape(ctx.score_state.value if ctx.score_state else '*')}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='row'><span class='chip'>Gesture: {html.escape(rec.gesture)}</span>"
                    f"<span class='chip'>Shout: {html.escape((rec.shout.value if isinstance(rec.shout, Shout) else str(rec.shout)) or 'None')}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"<div class='muted'>Talk: {html.escape(rec.team_talk or '(auto)')}</div>", unsafe_allow_html=True)
                # Show verbose engine trace for transparency
                if getattr(rec, "trace", None):
                    with st.expander("Trace"):
                        st.code("\n".join([str(t) for t in rec.trace[:200]]), language="text")
                if getattr(rec, "notes", None):
                    with st.expander("Why this"):
                        for n in rec.notes[:10]:
                            st.write(f"- {n}")
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.write(f"Filtered rules: {len(filtered)} / Total: {len(base_rules)}")