import streamlit as st
from datetime import datetime
from typing import Optional, Dict, Any, List

from domain.models import (
    Context,
    MatchStage,
    FavStatus,
    Venue,
    ScoreState,
    Shout,
    SpecialSituation,
    TalkAudience,
)
from domain.rules_engine import recommend, detect_fav_status
from services.session import SessionManager


def stage_from_minute(minute: Optional[int]) -> MatchStage:
    if minute is None:
        return MatchStage.PRE_MATCH
    if minute <= 0:
        return MatchStage.PRE_MATCH
    if minute < 25:
        return MatchStage.EARLY
    if minute < 65:
        return MatchStage.MID
    if minute < 85:
        return MatchStage.LATE
    if minute < 90:
        return MatchStage.VERY_LATE
    return MatchStage.FULL_TIME


st.title("🧱 Session Builder")
st.caption("Log snapshots and build a match session with stage-specific tabs. Submit once per match.")

# Light CSS for visual polish + tiny animation
st.markdown(
    """
    <style>
    .pm-card { position: relative; padding: 16px; border-radius: 12px; background: linear-gradient(135deg,#0f172a 0%, #111827 40%, #1f2937 100%); color: #e5e7eb; border: 1px solid #334155; overflow: hidden; }
    .pm-card:before { content: ""; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle at 20% 20%, rgba(59,130,246,0.12), transparent 40%); animation: pm-pulse 6s ease-in-out infinite; }
    @keyframes pm-pulse { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(5px,5px) scale(1.01); } }
    .pm-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .pm-title { font-weight: 600; font-size: 18px; }
    .chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; border:1px solid #334155; background:#0b1220; color:#e5e7eb; font-size: 12px; }
    .chip.badge { background:#111827; border-color:#374151; }
    .chip.win { background:#064e3b; border-color:#065f46; }
    .chip.draw { background:#1f2937; border-color:#374151; }
    .chip.loss { background:#7f1d1d; border-color:#991b1b; }
    .form-line { display:flex; gap:6px; }
    .meta { opacity:0.9; }
    .muted { color:#9ca3af; }
    .spacer { height:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

sm = SessionManager()

# Utilities
def has_decision(events: List[Dict[str, Any]], stage: MatchStage) -> bool:
    return any(e.get("type") == "decision" and (e.get("payload") or {}).get("stage") == stage.value for e in events)

def best_snapshot_for(events: List[Dict[str, Any]], predicate) -> Optional[Dict[str, Any]]:
    snaps = [e for e in events if e.get("type") == "snapshot"]
    snaps = [e for e in snaps if predicate(e)]
    if not snaps:
        return None
    return sorted(snaps, key=lambda e: (e.get("minute", 0), e.get("ts", "")))[-1]

def context_from_snapshot(base_ctx: Context, snap: Dict[str, Any], stage: MatchStage) -> Context:
    p = snap.get("payload", {})
    team = int(p.get("score_for", 0))
    opp = int(p.get("score_against", 0))
    if team > opp:
        ss = ScoreState.WINNING
    elif team < opp:
        ss = ScoreState.LOSING
    else:
        ss = ScoreState.DRAWING
    return Context(
        stage=stage,
        fav_status=base_ctx.fav_status,
        venue=base_ctx.venue,
        score_state=ss,
        minute=int(p.get("minute", 0)),
        possession_pct=p.get("possession_pct"),
        shots_for=p.get("shots_for"),
        shots_against=p.get("shots_against"),
        shots_on_target_for=p.get("shots_on_target_for"),
        shots_on_target_against=p.get("shots_on_target_against"),
        xg_for=p.get("xg_for"),
        xg_against=p.get("xg_against"),
        team_goals=team,
        opponent_goals=opp,
    )

def _get_base_ctx(active_session: Dict[str, Any] | None) -> Context:
    ctxd = (active_session or {}).get("context", {})
    fav_val = ctxd.get("fav_status", FavStatus.FAVOURITE.value)
    ven_val = ctxd.get("venue", Venue.HOME.value)
    fav = FavStatus.FAVOURITE if fav_val == FavStatus.FAVOURITE.value else FavStatus.UNDERDOG
    ven = Venue(ven_val)
    # Map lists back to enums when available
    specials_list = []
    for s in ctxd.get("special_situations", []) or []:
        try:
            specials_list.append(SpecialSituation(s))
        except Exception:
            pass
    pref_aud = None
    if ctxd.get("preferred_talk_audience"):
        try:
            pref_aud = TalkAudience(ctxd.get("preferred_talk_audience"))
        except Exception:
            pref_aud = None
    base = Context(
        stage=MatchStage.PRE_MATCH,
        fav_status=fav,
        venue=ven,
        minute=0,
        team_position=ctxd.get("team_position"),
        opponent_position=ctxd.get("opponent_position"),
        team_form=ctxd.get("team_form"),
        opponent_form=ctxd.get("opponent_form"),
        special_situations=specials_list,
        preferred_talk_audience=pref_aud,
        auto_fav_status=bool(ctxd.get("auto_fav_status", False)),
    )
    # If auto-detect is enabled for the active session, derive favourite now
    if base.auto_fav_status:
        try:
            det, _ = detect_fav_status(base)
            base.fav_status = det
        except Exception:
            pass
    return base

tabs = st.tabs(["Pre-Match", "First Half", "Half-Time", "Second Half", "Full-Time", "Timeline"])

# Pre-Match Tab
with tabs[0]:
    st.subheader("Pre-Match Setup & Talk")
    active = sm.get_active()
    col1, col2, col3 = st.columns(3)
    with col1:
        opponent = st.text_input("Opponent", value=(active or {}).get("name", ""))
    with col2:
        venue_options = [v.value for v in Venue]
        venue_val = (active and active.get("context", {}).get("venue")) or Venue.HOME.value
        venue_idx = venue_options.index(venue_val) if venue_val in venue_options else 0
        venue_sel = st.selectbox("Venue", options=venue_options, index=venue_idx)
    with col3:
        # Determine current auto-detect checkbox state (from session or saved context) to drive disabled state
        _ctxd_preview = (active or {}).get("context", {})
        auto_checked_state = bool(st.session_state.get("pm_auto_fav", _ctxd_preview.get("auto_fav_status", False)))
        fav_options = [FavStatus.FAVOURITE.value, FavStatus.UNDERDOG.value]
        fav_val = (active and active.get("context", {}).get("fav_status")) or FavStatus.FAVOURITE.value
        fav_idx = fav_options.index(fav_val) if fav_val in fav_options else 0
        fav_sel = st.selectbox("Status", options=fav_options, index=fav_idx, disabled=auto_checked_state)

    # Additional Pre-Match meta
    ctxd = (active or {}).get("context", {})
    pos_col1, pos_col2, pos_col3 = st.columns([1, 1, 1])
    with pos_col1:
        team_pos = st.number_input(
            "Your league position",
            min_value=1,
            max_value=24,
            value=int(ctxd.get("team_position", 1) or 1),
            step=1,
            key="pm_team_pos",
        )
    with pos_col2:
        opp_pos = st.number_input(
            "Opposition league position",
            min_value=1,
            max_value=24,
            value=int(ctxd.get("opponent_position", 1) or 1),
            step=1,
            key="pm_opp_pos",
        )
    with pos_col3:
        auto_fav = st.checkbox("Auto-detect favourite from context", value=bool(ctxd.get("auto_fav_status", False)), key="pm_auto_fav")

    form_col1, form_col2 = st.columns(2)
    def _norm_form(f: str) -> str:
        return "".join([c for c in (f or "").upper() if c in ("W","D","L")])[:5]
    with form_col1:
        team_form = st.text_input("Your recent form (e.g., WWDLD)", value=_norm_form(ctxd.get("team_form") or ""), key="pm_team_form")
    with form_col2:
        opp_form = st.text_input("Opposition recent form", value=_norm_form(ctxd.get("opponent_form") or ""), key="pm_opp_form")

    spec_col, aud_col = st.columns(2)
    with spec_col:
        special_opts = [s.value for s in SpecialSituation if s != SpecialSituation.NONE]
        selected_specs_vals = st.multiselect(
            "Special situations",
            options=special_opts,
            default=[s for s in (ctxd.get("special_situations") or []) if s in special_opts],
            key="pm_specs",
        )
    with aud_col:
        aud_opts = ["(auto)"] + [a.value for a in TalkAudience]
        aud_val = ctxd.get("preferred_talk_audience")
        aud_idx = 0 if not aud_val or aud_val not in aud_opts else aud_opts.index(aud_val)
        audience_sel = st.selectbox("Preferred talk audience", options=aud_opts, index=aud_idx, key="pm_audience")

    start_col, resume_col, _sp = st.columns([1, 1, 2])
    with start_col:
        if st.button("Start New Session", type="primary", disabled=bool(active) or not opponent.strip()):
            # Build a preliminary context to optionally derive favourite
            prelim_ctx = Context(
                stage=MatchStage.PRE_MATCH,
                fav_status=FavStatus.FAVOURITE if fav_sel == FavStatus.FAVOURITE.value else FavStatus.UNDERDOG,
                venue=Venue(venue_sel),
                minute=0,
                team_position=int(team_pos) if team_pos else None,
                opponent_position=int(opp_pos) if opp_pos else None,
                team_form=_norm_form(team_form),
                opponent_form=_norm_form(opp_form),
                special_situations=[SpecialSituation(s) for s in selected_specs_vals],
                preferred_talk_audience=None if audience_sel == "(auto)" else TalkAudience(audience_sel),
                auto_fav_status=bool(auto_fav),
            )
            # If auto-detect is enabled, ignore manual fav selection and use detected value
            if prelim_ctx.auto_fav_status:
                try:
                    _det_fav, _ = detect_fav_status(prelim_ctx)
                    prelim_ctx.fav_status = _det_fav
                except Exception:
                    pass
            st.session_state["_session"] = sm.start(prelim_ctx, name=opponent.strip())
            st.rerun()
    with resume_col:
        if active and st.button("Resume Active Session"):
            # Re-read to ensure latest context from disk
            current = sm.get_active()
            if current:
                st.session_state["_session"] = current
            st.rerun()

    # Visual Pre-Match summary (before talk)
    # Build a transient context from current inputs
    try:
        tmp_ctx = Context(
            stage=MatchStage.PRE_MATCH,
            fav_status=FavStatus.FAVOURITE if fav_sel == FavStatus.FAVOURITE.value else FavStatus.UNDERDOG,
            venue=Venue(venue_sel),
            minute=0,
            team_position=int(team_pos) if team_pos else None,
            opponent_position=int(opp_pos) if opp_pos else None,
            team_form=team_form,
            opponent_form=opp_form,
            special_situations=[SpecialSituation(s) for s in selected_specs_vals],
            preferred_talk_audience=None if audience_sel == "(auto)" else TalkAudience(audience_sel),
            auto_fav_status=bool(auto_fav),
        )
    except Exception:
        tmp_ctx = Context(stage=MatchStage.PRE_MATCH, fav_status=FavStatus.FAVOURITE, venue=Venue.HOME, minute=0)

    # Derive favourite if requested
    derived_text = ""
    derived_status = None
    if tmp_ctx.auto_fav_status:
        try:
            derived, expl = detect_fav_status(tmp_ctx)
            # Override favourite in preview context
            tmp_ctx.fav_status = derived
            derived_status = derived
            derived_text = f"<span class='chip badge'>Detected: {derived.value}</span> <span class='muted'>• {expl}</span>"
        except Exception:
            pass

    # Form chips renderer
    def _form_chips(s: str) -> str:
        if not s:
            return "<span class='muted'>—</span>"
        out = []
        for c in (s or "")[:5].upper():
            klass = 'draw'
            label = c
            if c == 'W':
                klass = 'win'
            elif c == 'L':
                klass = 'loss'
            out.append(f"<span class='chip {klass}'>{label}</span>")
        return f"<div class='form-line'>{''.join(out)}</div>"

    # Rank advantage (positive means you're better ranked)
    adv_html = ""
    if tmp_ctx.team_position and tmp_ctx.opponent_position:
        adv = tmp_ctx.opponent_position - tmp_ctx.team_position
        sign = "+" if adv >= 0 else ""
        adv_html = f"<span class='chip badge'>Rank advantage: {sign}{adv}</span>"

    # Specials chips
    spec_html = ""
    if tmp_ctx.special_situations:
        chips = [f"<span class='chip badge'>{s.value}</span>" for s in tmp_ctx.special_situations]
        spec_html = "".join(chips)

    # Audience chip
    aud_html = ""
    if tmp_ctx.preferred_talk_audience:
        aud_html = f"<span class='chip badge'>Audience: {tmp_ctx.preferred_talk_audience.value}</span>"

    st.markdown("---")
    # Optional manual save without locking
    save_col, _ = st.columns([1, 3])
    with save_col:
        if (active or {}) and st.button("Save Pre-Match Changes", key="pm_save"):
            sm.update_context(tmp_ctx)
            st.success("Pre-Match context saved.")
            st.rerun()
        st.markdown(
        f"""
        <div class='pm-card'>
          <div class='pm-row'>
            <div class='pm-title'>vs <strong>{opponent or '—'}</strong> • {venue_sel}</div>
                        <span class='chip badge'>Status: {(derived_status.value if (auto_fav and derived_status) else fav_sel)}{' (auto)' if auto_fav else ''}</span>
            {adv_html}
            {aud_html}
          </div>
          <div class='spacer'></div>
          <div class='pm-row meta'>
            <div>Form (You): {_form_chips(team_form)}</div>
          </div>
          <div class='pm-row meta'>
            <div>Form (Opp): {_form_chips(opp_form)}</div>
          </div>
          <div class='spacer'></div>
          <div class='pm-row'>{spec_html}</div>
          <div class='spacer'></div>
          <div class='pm-row'>{derived_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    active = sm.get_active()
    if active:
        events = active.get("events", [])
        # Use the current inputs (tmp_ctx) for the preview so changes reflect instantly
        base_ctx = tmp_ctx
        st.markdown("---")
        st.markdown("**Pre-Match Talk**")
        if has_decision(events, MatchStage.PRE_MATCH):
            st.success("Pre-Match decision locked")
        else:
            pre_rec = recommend(base_ctx)
            if pre_rec:
                st.write(f"Gesture: {pre_rec.gesture} • Shout: {pre_rec.shout.value if isinstance(pre_rec.shout, Shout) else pre_rec.shout}")
                if pre_rec.team_talk:
                    st.write(f"Talk: {pre_rec.team_talk}")
                # Rationale
                if getattr(pre_rec, "notes", None):
                    with st.expander("Why this"):
                        for n in pre_rec.notes[:6]:
                            st.write(f"- {n}")
                if st.button("Lock Pre-Match", key="lock_pm"):
                    # Persist the current inputs into the active session's context
                    sm.update_context(base_ctx)
                    sm.append_event({
                        "type": "decision",
                        "minute": 0,
                        "payload": {
                            "stage": MatchStage.PRE_MATCH.value,
                            "tone": "auto",
                            "gesture": pre_rec.gesture,
                            "phrase": pre_rec.team_talk,
                            "shout": Shout.NONE.value,
                        }
                    })
                    st.rerun()

# First Half Tab
with tabs[1]:
    active = sm.get_active()
    if not active:
        st.info("Start a session in Pre-Match first.")
    else:
        st.subheader("Add Snapshot (First Half)")
        # Prefill defaults from the latest FH snapshot (<=45') if available
        events = (sm.get_active() or {}).get("events", [])
        last_fh = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) <= 45)
        last_any = best_snapshot_for(events, lambda e: True)
        # Prefer last FH snapshot, otherwise fallback to last any snapshot if it's still in first half
        fallback_first_half = last_any if (last_any and int(last_any.get("minute", 0)) <= 45) else None
        last_fh_p = (last_fh or fallback_first_half or {}).get("payload", {})
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            # If we have a previous FH minute, suggest +5 up to 45
            suggested_min_fh = 10
            try:
                if last_fh_p:
                    prev_min = int(last_fh_p.get("minute", 10))
                    # Only use previous minute if it was first half; else keep default 10
                    if prev_min <= 45:
                        suggested_min_fh = min(45, prev_min + 5)
            except Exception:
                pass
            minute = st.number_input("Minute", min_value=0, max_value=45, value=int(suggested_min_fh), step=1, key="fh_min")
        with c2:
            team_goals = st.number_input("Goals For", min_value=0, max_value=20, value=int(last_fh_p.get("score_for", 0) or 0), step=1, key="fh_gf")
        with c3:
            opp_goals = st.number_input("Goals Against", min_value=0, max_value=20, value=int(last_fh_p.get("score_against", 0) or 0), step=1, key="fh_ga")
        with c4:
            possession = st.number_input("Possession %", min_value=0, max_value=100, value=int(last_fh_p.get("possession_pct", 50) or 50), step=1, key="fh_poss")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            shots_for = st.number_input("Shots For", min_value=0, max_value=50, value=int(last_fh_p.get("shots_for", 0) or 0), step=1, key="fh_sf")
        with c6:
            shots_against = st.number_input("Shots Against", min_value=0, max_value=50, value=int(last_fh_p.get("shots_against", 0) or 0), step=1, key="fh_sa")
        with c7:
            sot_for = st.number_input("On Target For", min_value=0, max_value=50, value=int(last_fh_p.get("shots_on_target_for", 0) or 0), step=1, key="fh_sof")
        with c8:
            sot_against = st.number_input("On Target Against", min_value=0, max_value=50, value=int(last_fh_p.get("shots_on_target_against", 0) or 0), step=1, key="fh_soa")

        c9, c10 = st.columns(2)
        with c9:
            xg_for = st.number_input("xG For", min_value=0.0, max_value=15.0, value=float(last_fh_p.get("xg_for", 0.0) or 0.0), step=0.05, format="%.2f", key="fh_xgf")
        with c10:
            xg_against = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=float(last_fh_p.get("xg_against", 0.0) or 0.0), step=0.05, format="%.2f", key="fh_xga")

        snap_note_fh = st.text_input("Snapshot note (optional)", key="fh_note")
        if st.button("Add Snapshot (FH)"):
            score_state = ScoreState.WINNING.value if team_goals > opp_goals else (ScoreState.LOSING.value if team_goals < opp_goals else ScoreState.DRAWING.value)
            sm.append_event({
                "type": "snapshot",
                "minute": int(minute),
                "payload": {
                    "minute": int(minute),
                    "score_for": int(team_goals),
                    "score_against": int(opp_goals),
                    "score_state": score_state,
                    "possession_pct": float(possession),
                    "shots_for": int(shots_for),
                    "shots_against": int(shots_against),
                    "shots_on_target_for": int(sot_for),
                    "shots_on_target_against": int(sot_against),
                    "xg_for": float(xg_for),
                    "xg_against": float(xg_against),
                    "note": snap_note_fh.strip() if snap_note_fh and snap_note_fh.strip() else None,
                }
            })
            st.success(f"Snapshot added for {minute}' (FH)")
            st.rerun()

        # Shout suggestion (FH)
        st.markdown("---")
        st.markdown("**In-Play Shout (FH)**")
        active = sm.get_active() or {}
        events = active.get("events", [])
        latest_snap = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) <= 45)
        if not latest_snap:
            st.caption("Add a snapshot to enable shout suggestions.")
        else:
            base_ctx = _get_base_ctx(active)
            live_ctx = context_from_snapshot(base_ctx, latest_snap, stage_from_minute(int(latest_snap.get("minute", 0))))
            if live_ctx.stage in (MatchStage.PRE_MATCH, MatchStage.FULL_TIME, MatchStage.HALF_TIME):
                live_ctx.stage = MatchStage.MID
            rec = recommend(live_ctx)
            if rec:
                st.write(f"Suggested shout: {rec.shout.value if isinstance(rec.shout, Shout) else rec.shout}")
                # Rationale
                if getattr(rec, "notes", None):
                    with st.expander("Why this"):
                        for n in rec.notes[:6]:
                            st.write(f"- {n}")
                if st.button("Add Shout (FH)"):
                    sm.append_event({
                        "type": "shout",
                        "minute": int(latest_snap.get("minute", 0)),
                        "payload": {"kind": rec.shout.value if isinstance(rec.shout, Shout) else str(rec.shout)}
                    })
                    st.rerun()

# Half-Time Tab
with tabs[2]:
    active = sm.get_active()
    if not active:
        st.info("Start a session in Pre-Match first.")
    else:
        st.subheader("Half-Time Talk")
        events = active.get("events", [])
        base_ctx = _get_base_ctx(active)
        if has_decision(events, MatchStage.HALF_TIME):
            st.success("Half-Time decision locked")
        else:
            ht_snap = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) <= 45)
            if not ht_snap:
                st.info("Add a snapshot at or before 45' to generate HT talk.")
                # Half-Time Snapshot form (minute fixed at 45), prefilled from latest FH snapshot
                last_fh = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) <= 45)
                last_fh_p = (last_fh or {}).get("payload", {})
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    ht_min = st.number_input("Minute", min_value=45, max_value=45, value=45, step=1, key="ht_min", disabled=True)
                with c2:
                    ht_gf = st.number_input("Goals For", min_value=0, max_value=20, value=int(last_fh_p.get("score_for", 0) or 0), step=1, key="ht_gf")
                with c3:
                    ht_ga = st.number_input("Goals Against", min_value=0, max_value=20, value=int(last_fh_p.get("score_against", 0) or 0), step=1, key="ht_ga")
                with c4:
                    ht_poss = st.number_input("Possession %", min_value=0, max_value=100, value=int(last_fh_p.get("possession_pct", 50) or 50), step=1, key="ht_poss")

                c5, c6, c7, c8 = st.columns(4)
                with c5:
                    ht_sf = st.number_input("Shots For", min_value=0, max_value=50, value=int(last_fh_p.get("shots_for", 0) or 0), step=1, key="ht_sf")
                with c6:
                    ht_sa = st.number_input("Shots Against", min_value=0, max_value=50, value=int(last_fh_p.get("shots_against", 0) or 0), step=1, key="ht_sa")
                with c7:
                    ht_sof = st.number_input("On Target For", min_value=0, max_value=50, value=int(last_fh_p.get("shots_on_target_for", 0) or 0), step=1, key="ht_sof")
                with c8:
                    ht_soa = st.number_input("On Target Against", min_value=0, max_value=50, value=int(last_fh_p.get("shots_on_target_against", 0) or 0), step=1, key="ht_soa")

                c9, c10 = st.columns(2)
                with c9:
                    ht_xgf = st.number_input("xG For", min_value=0.0, max_value=15.0, value=float(last_fh_p.get("xg_for", 0.0) or 0.0), step=0.05, format="%.2f", key="ht_xgf")
                with c10:
                    ht_xga = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=float(last_fh_p.get("xg_against", 0.0) or 0.0), step=0.05, format="%.2f", key="ht_xga")

                snap_note_ht = st.text_input("Snapshot note (optional)", key="ht_note")
                if st.button("Add Snapshot (HT)", key="add_ht_snap"):
                    score_state_ht = (
                        ScoreState.WINNING.value if ht_gf > ht_ga else (
                            ScoreState.LOSING.value if ht_gf < ht_ga else ScoreState.DRAWING.value
                        )
                    )
                    sm.append_event({
                        "type": "snapshot",
                        "minute": 45,
                        "payload": {
                            "minute": 45,
                            "score_for": int(ht_gf),
                            "score_against": int(ht_ga),
                            "score_state": score_state_ht,
                            "possession_pct": float(ht_poss),
                            "shots_for": int(ht_sf),
                            "shots_against": int(ht_sa),
                            "shots_on_target_for": int(ht_sof),
                            "shots_on_target_against": int(ht_soa),
                            "xg_for": float(ht_xgf),
                            "xg_against": float(ht_xga),
                            "note": snap_note_ht.strip() if snap_note_ht and snap_note_ht.strip() else None,
                        }
                    })
                    st.success("Half-Time snapshot added (45')")
                    st.rerun()
            else:
                ht_ctx = context_from_snapshot(base_ctx, ht_snap, MatchStage.HALF_TIME)
                ht_rec = recommend(ht_ctx)
                if ht_rec:
                    st.write(f"Gesture: {ht_rec.gesture} • Shout: {ht_rec.shout.value if isinstance(ht_rec.shout, Shout) else ht_rec.shout}")
                    if ht_rec.team_talk:
                        st.write(f"Talk: {ht_rec.team_talk}")
                    # Rationale
                    if getattr(ht_rec, "notes", None):
                        with st.expander("Why this"):
                            for n in ht_rec.notes[:6]:
                                st.write(f"- {n}")
                    # Optional: Edit/Log a Half-Time snapshot even if one exists
                    with st.expander("Add or Update Half-Time Snapshot (45')", expanded=False):
                        # Prefill from the existing HT snapshot payload; fallback to latest FH snapshot
                        default_src = ht_snap
                        if not default_src:
                            default_src = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) <= 45)
                        pdef = (default_src or {}).get("payload", {})
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            st.number_input("Minute", min_value=45, max_value=45, value=45, step=1, key="ht_edit_min", disabled=True)
                        with c2:
                            e_gf = st.number_input("Goals For", min_value=0, max_value=20, value=int(pdef.get("score_for", 0) or 0), step=1, key="ht_edit_gf")
                        with c3:
                            e_ga = st.number_input("Goals Against", min_value=0, max_value=20, value=int(pdef.get("score_against", 0) or 0), step=1, key="ht_edit_ga")
                        with c4:
                            e_poss = st.number_input("Possession %", min_value=0, max_value=100, value=int(pdef.get("possession_pct", 50) or 50), step=1, key="ht_edit_poss")

                        c5, c6, c7, c8 = st.columns(4)
                        with c5:
                            e_sf = st.number_input("Shots For", min_value=0, max_value=50, value=int(pdef.get("shots_for", 0) or 0), step=1, key="ht_edit_sf")
                        with c6:
                            e_sa = st.number_input("Shots Against", min_value=0, max_value=50, value=int(pdef.get("shots_against", 0) or 0), step=1, key="ht_edit_sa")
                        with c7:
                            e_sof = st.number_input("On Target For", min_value=0, max_value=50, value=int(pdef.get("shots_on_target_for", 0) or 0), step=1, key="ht_edit_sof")
                        with c8:
                            e_soa = st.number_input("On Target Against", min_value=0, max_value=50, value=int(pdef.get("shots_on_target_against", 0) or 0), step=1, key="ht_edit_soa")

                        c9, c10 = st.columns(2)
                        with c9:
                            e_xgf = st.number_input("xG For", min_value=0.0, max_value=15.0, value=float(pdef.get("xg_for", 0.0) or 0.0), step=0.05, format="%.2f", key="ht_edit_xgf")
                        with c10:
                            e_xga = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=float(pdef.get("xg_against", 0.0) or 0.0), step=0.05, format="%.2f", key="ht_edit_xga")

                        snap_note_ht2 = st.text_input("Snapshot note (optional)", key="ht_edit_note")
                        if st.button("Save Half-Time Snapshot (45')", key="save_ht_edit"):
                            score_state_ht2 = (
                                ScoreState.WINNING.value if e_gf > e_ga else (
                                    ScoreState.LOSING.value if e_gf < e_ga else ScoreState.DRAWING.value
                                )
                            )
                            sm.append_event({
                                "type": "snapshot",
                                "minute": 45,
                                "payload": {
                                    "minute": 45,
                                    "score_for": int(e_gf),
                                    "score_against": int(e_ga),
                                    "score_state": score_state_ht2,
                                    "possession_pct": float(e_poss),
                                    "shots_for": int(e_sf),
                                    "shots_against": int(e_sa),
                                    "shots_on_target_for": int(e_sof),
                                    "shots_on_target_against": int(e_soa),
                                    "xg_for": float(e_xgf),
                                    "xg_against": float(e_xga),
                                    "note": snap_note_ht2.strip() if snap_note_ht2 and snap_note_ht2.strip() else None,
                                }
                            })
                            st.success("Half-Time snapshot saved (45')")
                            st.rerun()
                    if st.button("Lock Half-Time", key="lock_ht"):
                        sm.append_event({
                            "type": "decision",
                            "minute": 45,
                            "payload": {
                                "stage": MatchStage.HALF_TIME.value,
                                "tone": "auto",
                                "gesture": ht_rec.gesture,
                                "phrase": ht_rec.team_talk,
                                "shout": Shout.NONE.value,
                            }
                        })
                        st.rerun()

# Second Half Tab
with tabs[3]:
    active = sm.get_active()
    if not active:
        st.info("Start a session in Pre-Match first.")
    else:
        st.subheader("Add Snapshot (Second Half)")
        # Prefill defaults from the latest SH snapshot (>=46') if available, otherwise last any snapshot
        events = (sm.get_active() or {}).get("events", [])
        last_sh = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) >= 46)
        if last_sh is None:
            last_sh = best_snapshot_for(events, lambda e: True)
        last_sh_p = (last_sh or {}).get("payload", {})
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            # If we have a previous SH minute, suggest +5 up to 120
            suggested_min_sh = 70
            try:
                if last_sh_p:
                    last_min_val = int(last_sh_p.get("minute", 70))
                    if last_min_val < 46:
                        # If previous snapshot was first-half, start SH at 46
                        suggested_min_sh = 46
                    else:
                        suggested_min_sh = min(120, last_min_val + 5)
            except Exception:
                pass
            minute2 = st.number_input("Minute", min_value=46, max_value=120, value=int(max(46, suggested_min_sh)), step=1, key="sh_min")
        with c2:
            team_goals2 = st.number_input("Goals For", min_value=0, max_value=20, value=int(last_sh_p.get("score_for", 0) or 0), step=1, key="sh_gf")
        with c3:
            opp_goals2 = st.number_input("Goals Against", min_value=0, max_value=20, value=int(last_sh_p.get("score_against", 0) or 0), step=1, key="sh_ga")
        with c4:
            possession2 = st.number_input("Possession %", min_value=0, max_value=100, value=int(last_sh_p.get("possession_pct", 50) or 50), step=1, key="sh_poss")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            shots_for2 = st.number_input("Shots For", min_value=0, max_value=50, value=int(last_sh_p.get("shots_for", 0) or 0), step=1, key="sh_sf")
        with c6:
            shots_against2 = st.number_input("Shots Against", min_value=0, max_value=50, value=int(last_sh_p.get("shots_against", 0) or 0), step=1, key="sh_sa")
        with c7:
            sot_for2 = st.number_input("On Target For", min_value=0, max_value=50, value=int(last_sh_p.get("shots_on_target_for", 0) or 0), step=1, key="sh_sof")
        with c8:
            sot_against2 = st.number_input("On Target Against", min_value=0, max_value=50, value=int(last_sh_p.get("shots_on_target_against", 0) or 0), step=1, key="sh_soa")

        c9, c10 = st.columns(2)
        with c9:
            xg_for2 = st.number_input("xG For", min_value=0.0, max_value=15.0, value=float(last_sh_p.get("xg_for", 0.0) or 0.0), step=0.05, format="%.2f", key="sh_xgf")
        with c10:
            xg_against2 = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=float(last_sh_p.get("xg_against", 0.0) or 0.0), step=0.05, format="%.2f", key="sh_xga")

        snap_note_sh = st.text_input("Snapshot note (optional)", key="sh_note")
        if st.button("Add Snapshot (SH)"):
            score_state2 = ScoreState.WINNING.value if team_goals2 > opp_goals2 else (ScoreState.LOSING.value if team_goals2 < opp_goals2 else ScoreState.DRAWING.value)
            sm.append_event({
                "type": "snapshot",
                "minute": int(minute2),
                "payload": {
                    "minute": int(minute2),
                    "score_for": int(team_goals2),
                    "score_against": int(opp_goals2),
                    "score_state": score_state2,
                    "possession_pct": float(possession2),
                    "shots_for": int(shots_for2),
                    "shots_against": int(shots_against2),
                    "shots_on_target_for": int(sot_for2),
                    "shots_on_target_against": int(sot_against2),
                    "xg_for": float(xg_for2),
                    "xg_against": float(xg_against2),
                    "note": snap_note_sh.strip() if snap_note_sh and snap_note_sh.strip() else None,
                }
            })
            st.success(f"Snapshot added for {minute2}' (SH)")
            st.rerun()

        # Shout suggestion (SH)
        st.markdown("---")
        st.markdown("**In-Play Shout (SH)**")
        active = sm.get_active() or {}
        events = active.get("events", [])
        latest_snap2 = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) >= 46)
        if not latest_snap2:
            st.caption("Add a snapshot to enable shout suggestions.")
        else:
            base_ctx = _get_base_ctx(active)
            live_ctx = context_from_snapshot(base_ctx, latest_snap2, stage_from_minute(int(latest_snap2.get("minute", 0))))
            if live_ctx.stage in (MatchStage.PRE_MATCH, MatchStage.FULL_TIME, MatchStage.HALF_TIME):
                live_ctx.stage = MatchStage.MID
            rec = recommend(live_ctx)
            if rec:
                st.write(f"Suggested shout: {rec.shout.value if isinstance(rec.shout, Shout) else rec.shout}")
                # Rationale
                if getattr(rec, "notes", None):
                    with st.expander("Why this"):
                        for n in rec.notes[:6]:
                            st.write(f"- {n}")
                if st.button("Add Shout (SH)"):
                    sm.append_event({
                        "type": "shout",
                        "minute": int(latest_snap2.get("minute", 0)),
                        "payload": {"kind": rec.shout.value if isinstance(rec.shout, Shout) else str(rec.shout)}
                    })
                    st.rerun()

# Full-Time Tab
with tabs[4]:
    active = sm.get_active()
    if not active:
        st.info("Start a session in Pre-Match first.")
    else:
        st.subheader("Full-Time Talk")
        events = active.get("events", [])
        base_ctx = _get_base_ctx(active)
        if has_decision(events, MatchStage.FULL_TIME):
            st.success("Full-Time decision locked")
        else:
            ft_snap = best_snapshot_for(events, lambda e: int(e.get("minute", 0)) >= 90)
            if not ft_snap:
                st.info("Add a snapshot at or after 90' to generate FT talk.")
                # Provide an inline snapshot form for FT
                # Prefill from the latest available snapshot if present
                last_any = best_snapshot_for(events, lambda e: True) if events else None
                last_p = (last_any or {}).get("payload", {})
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    ft_min = st.number_input("Minute", min_value=90, max_value=120, value=90, step=1, key="ft_min")
                with c2:
                    ft_gf = st.number_input("Goals For", min_value=0, max_value=20, value=int(last_p.get("score_for", 0)), step=1, key="ft_gf")
                with c3:
                    ft_ga = st.number_input("Goals Against", min_value=0, max_value=20, value=int(last_p.get("score_against", 0)), step=1, key="ft_ga")
                with c4:
                    ft_poss = st.number_input("Possession %", min_value=0, max_value=100, value=int(last_p.get("possession_pct", 50) or 50), step=1, key="ft_poss")

                c5, c6, c7, c8 = st.columns(4)
                with c5:
                    ft_sf = st.number_input("Shots For", min_value=0, max_value=50, value=int(last_p.get("shots_for", 0)), step=1, key="ft_sf")
                with c6:
                    ft_sa = st.number_input("Shots Against", min_value=0, max_value=50, value=int(last_p.get("shots_against", 0)), step=1, key="ft_sa")
                with c7:
                    ft_sof = st.number_input("On Target For", min_value=0, max_value=50, value=int(last_p.get("shots_on_target_for", 0)), step=1, key="ft_sof")
                with c8:
                    ft_soa = st.number_input("On Target Against", min_value=0, max_value=50, value=int(last_p.get("shots_on_target_against", 0)), step=1, key="ft_soa")

                c9, c10 = st.columns(2)
                with c9:
                    ft_xgf = st.number_input("xG For", min_value=0.0, max_value=15.0, value=float(last_p.get("xg_for", 0.0) or 0.0), step=0.05, format="%.2f", key="ft_xgf")
                with c10:
                    ft_xga = st.number_input("xG Against", min_value=0.0, max_value=15.0, value=float(last_p.get("xg_against", 0.0) or 0.0), step=0.05, format="%.2f", key="ft_xga")

                snap_note_ft = st.text_input("Snapshot note (optional)", key="ft_note")
                if st.button("Add Snapshot (FT)", key="add_ft_snap"):
                    score_state_ft = (
                        ScoreState.WINNING.value if ft_gf > ft_ga else (
                            ScoreState.LOSING.value if ft_gf < ft_ga else ScoreState.DRAWING.value
                        )
                    )
                    sm.append_event({
                        "type": "snapshot",
                        "minute": int(ft_min),
                        "payload": {
                            "minute": int(ft_min),
                            "score_for": int(ft_gf),
                            "score_against": int(ft_ga),
                            "score_state": score_state_ft,
                            "possession_pct": float(ft_poss),
                            "shots_for": int(ft_sf),
                            "shots_against": int(ft_sa),
                            "shots_on_target_for": int(ft_sof),
                            "shots_on_target_against": int(ft_soa),
                            "xg_for": float(ft_xgf),
                            "xg_against": float(ft_xga),
                            "note": snap_note_ft.strip() if snap_note_ft and snap_note_ft.strip() else None,
                        }
                    })
                    st.success(f"Snapshot added for {ft_min}' (FT)")
                    st.rerun()
            else:
                ft_ctx = context_from_snapshot(base_ctx, ft_snap, MatchStage.FULL_TIME)
                ft_rec = recommend(ft_ctx)
                if ft_rec:
                    st.write(f"Gesture: {ft_rec.gesture} • Shout: {ft_rec.shout.value if isinstance(ft_rec.shout, Shout) else ft_rec.shout}")
                    if ft_rec.team_talk:
                        st.write(f"Talk: {ft_rec.team_talk}")
                    # Rationale
                    if getattr(ft_rec, "notes", None):
                        with st.expander("Why this"):
                            for n in ft_rec.notes[:6]:
                                st.write(f"- {n}")
                    if st.button("Lock Full-Time", key="lock_ft"):
                        sm.append_event({
                            "type": "decision",
                            "minute": int(ft_snap.get("minute", 90)),
                            "payload": {
                                "stage": MatchStage.FULL_TIME.value,
                                "tone": "auto",
                                "gesture": ft_rec.gesture,
                                "phrase": ft_rec.team_talk,
                                "shout": Shout.NONE.value,
                            }
                        })
                        st.rerun()

# Timeline Tab
with tabs[5]:
    st.subheader("Timeline")
    active = sm.get_active() or {}
    events = active.get("events", [])
    if not events:
        st.caption("No events yet. Add snapshots or lock decisions.")
    else:
        for e in sorted(events, key=lambda x: (x.get("minute", 0), x.get("ts", ""))):
            minute_label = f"{e.get('minute', 0)}'" if e.get("minute") is not None else "—"
            if e.get("type") == "snapshot":
                p = e.get("payload", {})
                score = f"{p.get('score_for', 0)}–{p.get('score_against', 0)}"
                stats = f"Poss {int(p.get('possession_pct', 0))}% | Shots {p.get('shots_for', 0)}({p.get('shots_on_target_for', 0)}) vs {p.get('shots_against', 0)}({p.get('shots_on_target_against', 0)}) | xG {p.get('xg_for', 0.0):.2f} vs {p.get('xg_against', 0.0):.2f}"
                note_txt = p.get('note')
                note_str = f" • Note: {note_txt}" if note_txt else ""
                st.write(f"- {minute_label} Snapshot — {score} • {stats}{note_str}")
            else:
                st.write(f"- {minute_label} {e.get('type').title()} — {e.get('payload', {})}")

    st.markdown("---")
    st.subheader("Submit Session")
    notes = st.text_area("Notes (optional)")
    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("Submit & Archive", type="primary"):
            session = sm.complete(notes=notes)
            st.success(f"Session {session.get('id')} archived at {datetime.utcnow().isoformat()}Z")
            st.info("You can start a new session in Pre-Match.")
    with cols[1]:
        if st.button("Cancel Active Session", type="secondary"):
            from services.session import ACTIVE_FILE
            if ACTIVE_FILE.exists():
                ACTIVE_FILE.unlink(missing_ok=True)
            st.warning("Active session cancelled.")
            st.rerun()
