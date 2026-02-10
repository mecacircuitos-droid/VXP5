import time
from typing import Callable

import streamlit as st

from .sim import (
    BLADES,
    REGIMES,
    REGIME_LABEL,
    BO105_DISPLAY_RPM,
    default_adjustments,
    simulate_measurement,
)
from .reports import legacy_results_text, legacy_results_plain_text, legacy_results_html, clock_label
from .plots import plot_measurements_panel, plot_track_marker, plot_track_graph, plot_polar, plot_polar_compare
from .solver import all_ok, regime_status


def _status_icon_html(status: str | None) -> str:
    """Return an inline SVG approximating the legacy VXP status symbols."""

    if status is None:
        return ""

    # Colors approximate the legacy documentation screenshots.
    if status == "OK":
        fill = "#18b918"  # green
        # Check mark
        return (
            "<svg width='22' height='22' viewBox='0 0 24 24' "
            "xmlns='http://www.w3.org/2000/svg'>"
            f"<path fill='{fill}' d='M9.0 16.2 4.8 12.0 3.4 13.4 9.0 19 21 7 "
            "19.6 5.6z'/></svg>"
        )

    if status == "WARN":
        fill = "#18b918"  # green exclamation (as in help legend)
        return (
            "<svg width='22' height='22' viewBox='0 0 24 24' "
            "xmlns='http://www.w3.org/2000/svg'>"
            f"<path fill='{fill}' d='M12 2a2 2 0 0 1 2 2v10a2 2 0 0 1-4 0V4a2 2 0 0 1 2-2z'/>"
            f"<circle fill='{fill}' cx='12' cy='20' r='2'/>"
            "</svg>"
        )

    if status == "STOP":
        red = "#d11818"
        # Octagon + exclamation
        return (
            "<svg width='22' height='22' viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'>"
            f"<path fill='{red}' d='M7.0 2h10l5 5v10l-5 5H7l-5-5V7z'/>"
            "<path fill='#fff' d='M12 6.5c.7 0 1.25.55 1.25 1.25v6.7c0 .7-.55 1.25-1.25 1.25S10.75 15.15 10.75 14.45v-6.7C10.75 7.05 11.3 6.5 12 6.5z'/>"
            "<circle fill='#fff' cx='12' cy='18.9' r='1.4'/>"
            "</svg>"
        )

    # DONE / fallback: black check
    return (
        "<svg width='22' height='22' viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'>"
        "<path fill='#111' d='M9.0 16.2 4.8 12.0 3.4 13.4 9.0 19 21 7 19.6 5.6z'/>"
        "</svg>"
    )


# ---------------------------
# Navigation / state
# ---------------------------

def go(screen: str, **kwargs) -> None:
    st.session_state.vxp_screen = screen
    for k, v in kwargs.items():
        st.session_state[k] = v


def init_state() -> None:
    st.session_state.setdefault("vxp_screen", "home")
    st.session_state.setdefault("vxp_run", 1)
    st.session_state.setdefault("vxp_runs", {1: {}})
    st.session_state.setdefault("vxp_completed_by_run", {1: set()})
    st.session_state.setdefault("vxp_view_run", 1)

    st.session_state.setdefault("vxp_adjustments", default_adjustments())
    st.session_state.setdefault("vxp_pending_regime", None)
    st.session_state.setdefault("vxp_acq_in_progress", False)
    st.session_state.setdefault("vxp_acq_done", False)

    # Aircraft Info / Note Codes (legacy dialogs)
    st.session_state.setdefault(
        "vxp_aircraft",
        {
            "weight": 0.0,
            "cg": 0.0,
            "hours": 0.0,
            "initials": "",
        },
    )
    st.session_state.setdefault("vxp_note_codes", set())


def current_run_data(run: int):
    return st.session_state.vxp_runs.setdefault(run, {})


def completed_set(run: int):
    return st.session_state.vxp_completed_by_run.setdefault(run, set())


def run_selector_inline(key: str = "run_selector") -> int:
    runs = sorted(st.session_state.vxp_runs.keys())
    cur = int(st.session_state.vxp_view_run)
    if cur not in runs:
        cur = runs[0]
        st.session_state.vxp_view_run = cur
    idx = runs.index(cur)
    r = st.selectbox("Run", runs, index=idx, key=key)
    st.session_state.vxp_view_run = int(r)
    return int(r)


# ---------------------------
# Window chrome helpers
# ---------------------------

def win_caption(title: str, active: bool) -> None:
    cls = "active" if active else "inactive"
    st.markdown(
        f"<div class='vxp-win-caption {cls}'>"
        f"<div>{title}</div>"
        "<div class='vxp-closebox'>✕</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def right_close_button(
    label: str,
    *,
    target: str | None = None,
    on_click: Callable[[], None] | None = None,
    key: str | None = None,
) -> None:
    """Classic right-aligned button (usually Close).

    Streamlit can raise StreamlitDuplicateElementKey when multiple elements
    end up with the same implicit key. To make the app robust across Streamlit
    versions and navigation patterns, we always provide an explicit key.
    """
    screen = str(st.session_state.get("vxp_screen", ""))
    if key is None:
        safe = "".join(ch if ch.isalnum() else "_" for ch in label.lower())
        key = f"btn_{screen}_{safe}_right"

    cols = st.columns([0.75, 0.25])
    with cols[1]:
        if st.button(label, use_container_width=True, key=key):
            if target is not None:
                go(target)
            if on_click is not None:
                on_click()
            st.rerun()


"""UI rendering.

Nota importante sobre Streamlit:
  La superposición tipo MDI (varias ventanas apiladas) requiere CSS avanzado
  que no es consistente entre navegadores. Para evitar que la “ventana nueva”
  se abra debajo (en vez de superponerse), la UI se renderiza como UNA única
  ventana principal cuyo contenido cambia según la navegación.
"""


# ---------------------------
# Desktop (single-window)
# ---------------------------

def render_desktop() -> None:
    """Render a single main window (no overlapping popups)."""

    # IMPORTANT (Streamlit): we cannot "wrap" widgets inside an open <div>
    # created by st.markdown. Doing so produces empty boxes and pushes the
    # widgets below the intended frame (exactly what you saw).
    #
    # We instead use a real Streamlit container (optionally with border=True)
    # and skin that container via CSS.
    try:
        desk = st.container(border=True)
    except TypeError:
        desk = st.container()

    with desk:
        # Marker used by CSS (safe even if :has is not available).
        st.markdown("<div class='vxp-desktop-marker'></div>", unsafe_allow_html=True)

        if st.session_state.vxp_screen == "home":
            render_select_procedure_window(active=True)
        else:
            render_active_window()


def render_select_procedure_window(active: bool) -> None:
    win_caption("Select Procedure:", active=active)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # (3) Botones centrados como en el VXP original (lista central, sin columna vacía gigante)
    pad_l, mid, pad_r = st.columns([0.14, 0.72, 0.14], gap="small")

    with mid:
        if st.button("Aircraft Info", use_container_width=True, key="home_aircraft_info"):
            go("aircraft_info")
            st.rerun()
        if st.button("Main Rotor Balance Run 1", use_container_width=True, key="home_mr_run1"):
            go("mr_menu")
            st.rerun()

        # (4) En el original solo aparece Tail Rotor Balance Run 1.
        if st.button("Tail Rotor Balance Run 1", use_container_width=True, key="home_tr_run1"):
            go("not_impl")
            st.rerun()

        if st.button("T/R Driveshaft Balance Run 1", use_container_width=True, key="home_drv_run1"):
            go("not_impl")
            st.rerun()
        if st.button("Vibration Signatures", use_container_width=True, key="home_vib_sig"):
            go("not_impl")
            st.rerun()
        if st.button("Measurements Only", use_container_width=True, key="home_meas_only"):
            go("not_impl")
            st.rerun()
        if st.button("Setup / Utilities", use_container_width=True, key="home_setup_utils"):
            go("not_impl")
            st.rerun()


def render_active_window() -> None:
    screen = st.session_state.vxp_screen
    if screen == "mr_menu":
        screen_mr_menu_window()
    elif screen == "collect":
        screen_collect_window()
    elif screen == "acquire":
        # Backward compatibility: older builds navigated to an explicit
        # ACQUIRE screen. We now render acquisition as a modal inside COLLECT
        # to avoid duplicate button panes.
        go("collect")
        st.rerun()
    elif screen == "meas_list":
        screen_meas_list_window()
    elif screen == "meas_graph":
        screen_meas_graph_window()
    elif screen == "settings":
        screen_settings_window()
    elif screen == "solution":
        screen_solution_window()
    elif screen == "solution_text":
        screen_solution_text_window()
    elif screen == "next_run_prompt":
        screen_next_run_window()
    elif screen == "aircraft_info":
        screen_aircraft_info_window()
    elif screen == "note_codes":
        screen_note_codes_window()
    else:
        screen_not_impl_window()


# ---------------------------
# Procedure screens (inside the active window)
# ---------------------------

def _centered_buttons(labels_and_targets):
    """Helper to keep buttons from becoming too wide."""
    left, mid, right = st.columns([0.10, 0.80, 0.10])
    with mid:
        for label, target in labels_and_targets:
            # Explicit key avoids StreamlitDuplicateElementKey on some builds.
            screen = str(st.session_state.get("vxp_screen", ""))
            safe_t = "".join(ch if ch.isalnum() else "_" for ch in str(target))
            k = f"btn_{screen}_{safe_t}"
            if st.button(label, use_container_width=True, key=k):
                go(target)
                st.rerun()


def screen_mr_menu_window():
    run = int(st.session_state.vxp_run)
    win_caption(f"Main Rotor Balance Run {run}", active=True)
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='display:flex; justify-content:space-between; font-weight:900;'>"
        "<div>Tracking &amp; Balance – Option B</div>"
        f"<div>Run {run}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    _centered_buttons(
        [
            ("COLLECT", "collect"),
            ("MEASUREMENTS LIST", "meas_list"),
            ("MEASUREMENTS GRAPH", "meas_graph"),
            ("SETTINGS", "settings"),
            ("SOLUTION", "solution"),
            ("NEXT RUN", "next_run_prompt"),
        ]
    )

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    right_close_button("Close", on_click=lambda: go("home"))


def screen_collect_window():
    run = int(st.session_state.vxp_run)
    # When a regime is selected, we show the acquisition dialog to the right
    # **without changing screen**. This prevents rendering the COLLECT list twice
    # (a common Streamlit layout pitfall) and matches the legacy feel.
    pending = st.session_state.get("vxp_pending_regime")

    data = current_run_data(run)
    done = completed_set(run)

    # IMPORTANT (Streamlit): keep a stable layout path between reruns.
    # If we switch between st.container() and st.columns(), Streamlit can
    # leave the previous layout on the page, producing a duplicated (faded)
    # button pane like the one you reported. We always render the same
    # two-column structure and simply leave the right column empty when
    # no regime is being acquired.
    left, right = st.columns([0.44, 0.56], gap="medium")

    # ---------------- Left: COLLECT list ----------------
    with left:
        win_caption(f"RPM  {BO105_DISPLAY_RPM:.1f}", active=(pending is None))
        st.markdown(
            f"<div class='vxp-label' style='margin-top:8px;'>Main Rotor: Run {run} &nbsp;&nbsp;&nbsp; Day Mode</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        # While the acquisition dialog is open, keep the list visible but disable
        # the buttons (legacy behaved like a modal dialog).
        disable_list = pending is not None

        for r in REGIMES:
            cols = st.columns([0.84, 0.16])
            with cols[0]:
                if st.button(
                    REGIME_LABEL[r],
                    use_container_width=True,
                    disabled=disable_list,
                    key=f"reg_{run}_{r}",
                ):
                    st.session_state.vxp_pending_regime = r
                    st.session_state.vxp_acq_in_progress = False
                    st.session_state.vxp_acq_done = (r in done)
                    st.rerun()
            with cols[1]:
                icon = _status_icon_html(regime_status(r, data.get(r)))
                st.markdown(
                    "<div style='height:40px; display:flex; align-items:center; justify-content:center;'>"
                    + (icon if r in done else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )

        if run == 3 and len(done) == len(REGIMES) and all_ok(current_run_data(3)):
            st.markdown(
                "<div class='vxp-label' style='margin-top:10px;'>✓ RUN 3 COMPLETE — PARAMETERS OK</div>",
                unsafe_allow_html=True,
            )

        # Only show COLLECT Close when not in the modal acquisition dialog.
        if pending is None:
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            right_close_button("Close", on_click=lambda: go("mr_menu"))

    # ---------------- Right: Acquisition dialog (modal) ----------------
    if pending:
        with right:
            _render_acquire_dialog(run, pending)
    else:
        # Clear the right pane explicitly so Streamlit doesn't keep old content
        # when returning from the modal dialog.
        with right:
            st.empty()


def _render_acquire_dialog(run: int, regime: str) -> None:
    """Render the legacy-like ACQUIRING/DONE dialog (used inside COLLECT)."""

    data = current_run_data(run)
    done = completed_set(run)
    already_taken = regime in done

    # Title bar stays as ACQUIRING (legacy). Content will show DONE when finished.
    win_caption("ACQUIRING …", active=True)
    st.markdown(
        f"<div class='vxp-label' style='margin-top:8px;'>{REGIME_LABEL[regime]}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='vxp-label'>RPM {BO105_DISPLAY_RPM:.0f}</div>", unsafe_allow_html=True)

    box = st.empty()
    progress_ph = st.empty()

    # If the regime is already measured, just show the DONE summary (no re-measure).
    if already_taken:
        st.session_state.vxp_acq_done = True

    if not st.session_state.get("vxp_acq_done", False):
        box.markdown(
            "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
            "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
            "ACQUIRING ...\n"
            f"RPM {BO105_DISPLAY_RPM:.0f}\n"
            "\n"
            "ROLL (A-B)        1P\n"
            "ACQUIRING\n"
            "\n"
            "M/R LAT           1P\n"
            "ACQUIRING\n"
            "--------------------------------\n"
            "M/R OBT\n"
            "ACQUIRING\n"
            "</div>",
            unsafe_allow_html=True,
        )

        # Acquisition time: bottom progress bar (legacy feel).
        duration_s = 6.5
        steps = 65
        prog = progress_ph.progress(0)
        for i in range(steps):
            prog.progress(int((i + 1) * 100 / steps))
            time.sleep(duration_s / steps)
        progress_ph.empty()

        meas = simulate_measurement(run, regime, st.session_state.vxp_adjustments)
        current_run_data(run)[regime] = meas
        completed_set(run).add(regime)

        st.session_state.vxp_acq_done = True
        st.rerun()

    # DONE summary
    m = current_run_data(run).get(regime)
    status = regime_status(regime, m)
    icon = _status_icon_html(status)

    if m is not None:
        amp = float(m.balance.amp_ips)
        ph = float(m.balance.phase_deg)
        trk = m.track_mm
        box.markdown(
            "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
            "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
            "ACQUISITION DONE\n"
            "\n"
            "M/R LAT           1P\n"
            f"{amp:0.2f} @ {clock_label(ph)}\n"
            "\n"
            "M/R TRACK HEIGHT  mm rel. YEL\n"
            f"BLU {trk['BLU']:+5.1f}   GRN {trk['GRN']:+5.1f}   YEL {trk['YEL']:+5.1f}   RED {trk['RED']:+5.1f}\n"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        box.markdown(
            "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
            "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
            "ACQUISITION DONE\n"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    cols = st.columns([0.70, 0.30])
    with cols[0]:
        st.markdown(
            "<div style='height:34px; display:flex; align-items:center; gap:8px; justify-content:flex-start;'>"
            + (icon if icon else "")
            + "</div>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        if st.button("Close", use_container_width=True, key=f"acq_close_{run}_{regime}"):
            st.session_state.vxp_pending_regime = None
            st.session_state.vxp_acq_done = False
            st.rerun()

def screen_acquire_window():
    run = int(st.session_state.vxp_run)
    regime = st.session_state.get("vxp_pending_regime")
    if not regime:
        right_close_button("Close", on_click=lambda: go("collect"))
        return

    left, right = st.columns([0.44, 0.56], gap="medium")

    data = current_run_data(run)
    done = completed_set(run)
    already_taken = regime in done

    # ---------------- Left background list (static) ----------------
    with left:
        win_caption(f"RPM  {BO105_DISPLAY_RPM:.1f}", active=False)
        st.markdown(
            f"<div class='vxp-label' style='margin-top:8px;'>Main Rotor: Run {run} &nbsp;&nbsp;&nbsp; Day Mode</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        for r in REGIMES:
            cols = st.columns([0.84, 0.16])
            with cols[0]:
                st.button(REGIME_LABEL[r], use_container_width=True, disabled=True, key=f"acq_bg_{run}_{r}")
            with cols[1]:
                icon = _status_icon_html(regime_status(r, data.get(r)))
                st.markdown(
                    "<div style='height:40px; display:flex; align-items:center; justify-content:center;'>"
                    + (icon if r in done else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )

    # ---------------- Right acquisition dialog ----------------
    with right:
        # Title bar stays as ACQUIRING (like the legacy dialog). The content will show DONE when finished.
        win_caption("ACQUIRING …", active=True)
        st.markdown(
            f"<div class='vxp-label' style='margin-top:8px;'>{REGIME_LABEL[regime]}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='vxp-label'>RPM {BO105_DISPLAY_RPM:.0f}</div>", unsafe_allow_html=True)

        box = st.empty()
        progress_ph = st.empty()

        # If the regime is already measured, just show the DONE summary (no re-measure).
        if already_taken:
            st.session_state.vxp_acq_done = True

        if not st.session_state.get("vxp_acq_done", False):
            # Static ACQUIRING screen (two windows side-by-side, no fade).
            box.markdown(
                "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
                "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
                "ACQUIRING ...\n"
                f"RPM {BO105_DISPLAY_RPM:.0f}\n"
                "\n"
                "ROLL (A-B)        1P\n"
                "ACQUIRING\n"
                "\n"
                "M/R LAT           1P\n"
                "ACQUIRING\n"
                "--------------------------------\n"
                "M/R OBT\n"
                "ACQUIRING\n"
                "</div>",
                unsafe_allow_html=True,
            )

            # Acquisition time: show a bottom progress bar (legacy feel) and run slightly longer.
            duration_s = 6.5
            steps = 65
            prog = progress_ph.progress(0)
            for i in range(steps):
                prog.progress(int((i + 1) * 100 / steps))
                time.sleep(duration_s / steps)
            progress_ph.empty()

            meas = simulate_measurement(run, regime, st.session_state.vxp_adjustments)
            current_run_data(run)[regime] = meas
            completed_set(run).add(regime)

            st.session_state.vxp_acq_done = True
            st.rerun()

        # DONE summary (legacy-like)
        m = current_run_data(run).get(regime)
        status = regime_status(regime, m)
        icon = _status_icon_html(status)

        if m is not None:
            # Legacy-style DONE summary (amplitude @ clock-position, plus a compact track snippet)
            amp = float(m.balance.amp_ips)
            ph = float(m.balance.phase_deg)
            trk = m.track_mm

            box.markdown(
                "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
                "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
                "ACQUISITION DONE\n"
                "\n"
                "M/R LAT           1P\n"
                f"{amp:0.2f} @ {clock_label(ph)}\n"
                "\n"
                "M/R TRACK HEIGHT  mm rel. YEL\n"
                f"BLU {trk['BLU']:+5.1f}   GRN {trk['GRN']:+5.1f}   YEL {trk['YEL']:+5.1f}   RED {trk['RED']:+5.1f}\n"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            box.markdown(
                "<div class='vxp-mono' style='white-space:pre; border-top:2px solid #808080; border-left:2px solid #808080; "
                "border-right:2px solid #ffffff; border-bottom:2px solid #ffffff; padding:10px; background:#c0c0c0;'>"
                "ACQUISITION DONE\n"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        # Close button always visible under the box.
        cols = st.columns([0.70, 0.30])
        with cols[0]:
            st.markdown(
                f"<div style='height:34px; display:flex; align-items:center; gap:8px; justify-content:flex-start;'>"
                f"{icon if icon else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("Close", use_container_width=True, key=f"acq_close_{run}_{regime}"):
                st.session_state.vxp_pending_regime = None
                st.session_state.vxp_acq_done = False
                go("collect")
                st.rerun()

def screen_meas_list_window():
    win_caption("MEASUREMENTS LIST", active=True)
    view_run = run_selector_inline(key="run_selector_generic")
    data = current_run_data(view_run)
    if not data:
        st.write("No measurements for this run yet. Go to COLLECT.")
        right_close_button("Close", on_click=lambda: go("mr_menu"))
        return
    # User request: show the report inside a NORMAL textbox (white inset area)
    # like the early versions. We therefore strip HTML coloring and render as
    # a disabled text_area, which is stable across Streamlit versions.
    st.text_area(
        "",
        value=legacy_results_plain_text(view_run, data),
        height=420,
        key=f"meas_list_box_{view_run}",
        disabled=True,
        label_visibility="collapsed",
    )
    right_close_button("Close", on_click=lambda: go("mr_menu"))


def screen_meas_graph_window():
    win_caption("MEASUREMENTS GRAPH", active=True)

    # Compact controls (Streamlit defaults are too tall for XGA).
    st.markdown(
        """
<style>
/* Compact selectboxes only for this screen */
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] div[role="combobox"]{
  min-height:24px !important;
  height:24px !important;
  font-size:11px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] div[role="combobox"] > div{
  padding-top:0 !important;
  padding-bottom:0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # --- Top controls row (legacy VXP-like; Maximize removed for BO105) ---
    # Legacy screen shows a compact Regime selector for the Track plots.
    c1, c2, c3 = st.columns([0.18, 0.22, 0.60], gap="small")

    with c1:
        st.markdown(
            "<div class='vxp-label' style='font-size:12px; margin:0 0 2px 0;'>Run</div>",
            unsafe_allow_html=True,
        )
        runs = sorted(st.session_state.vxp_runs.keys())
        cur = int(st.session_state.vxp_view_run)
        if cur not in runs:
            cur = runs[0]
            st.session_state.vxp_view_run = cur
        idx = runs.index(cur)
        view_run = int(
            st.selectbox(
                "",
                runs,
                index=idx,
                key="run_selector_meas_graph",
                label_visibility="collapsed",
            )
        )
        st.session_state.vxp_view_run = view_run

    data = current_run_data(view_run)
    if not data:
        st.write("No measurements for this run yet. Go to COLLECT.")
        right_close_button("Close", on_click=lambda: go("mr_menu"))
        return

    available = [r for r in REGIMES if r in data]

    # Selected balance/track measurement (default to Ground if present).
    st.session_state.setdefault("meas_graph_sel_regime", "GROUND")
    sel_regime = str(st.session_state.get("meas_graph_sel_regime", "GROUND"))
    if sel_regime not in available:
        sel_regime = "GROUND" if "GROUND" in available else available[0]
        st.session_state.meas_graph_sel_regime = sel_regime

    with c2:
        st.markdown(
            "<div class='vxp-label' style='font-size:12px; margin:0 0 2px 0;'>Blade Ref1</div>",
            unsafe_allow_html=True,
        )
        # Default to YEL (matches the legacy screen)
        blade_ref = st.selectbox(
            "",
            options=BLADES,
            index=BLADES.index("YEL") if "YEL" in BLADES else 0,
            key="meas_graph_blade_ref",
            label_visibility="collapsed",
        )

    with c3:
        st.markdown(
            "<div class='vxp-label' style='font-size:12px; margin:0 0 2px 0;'>Regime</div>",
            unsafe_allow_html=True,
        )
        b_l, b_r = st.columns([0.35, 0.65], gap="small")
        with b_l:
            # Button-based selector (legacy feel): cycles Ground -> Hover -> Horizontal
            if st.button("Select Bal Meas", use_container_width=True, key="meas_graph_select_bal_top"):
                if available:
                    i = available.index(sel_regime) if sel_regime in available else 0
                    st.session_state.meas_graph_sel_regime = available[(i + 1) % len(available)]
                st.rerun()
        with b_r:
            st.markdown(
                f"<div class='vxp-label' style='font-size:12px; margin-top:4px;'>"
                f"{REGIME_LABEL.get(sel_regime, sel_regime)}"
                "</div>",
                unsafe_allow_html=True,
            )

    compare = {r: data[r] for r in REGIMES if r in data}

    # --- Layout (legacy-style): list on the left, combined figure on the right. ---
    fig = plot_measurements_panel(compare, sel_regime, blade_ref=blade_ref)
    left, right = st.columns([0.54, 0.46], gap="medium")

    with left:
        # Render as HTML so the Adjustments block can use a stable table layout.
        st.markdown(legacy_results_html(view_run, data), unsafe_allow_html=True)

    with right:
        st.pyplot(fig, clear_figure=True)
        # Close button aligned bottom-right (legacy feel).
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        cols = st.columns([0.78, 0.22])
        with cols[1]:
            if st.button("Close", use_container_width=True, key="meas_graph_close_bottom"):
                go("mr_menu")
                st.rerun()



def screen_settings_window():
    win_caption("SETTINGS", active=True)
    # User requested: only the Run selector (no flight/regime selector).
    run_selector_inline(key="run_selector_settings")

    # We keep adjustments internally per-regime, but the SETTINGS editor applies
    # the same values to all regimes so the UI matches the legacy feel.
    base_regime = REGIMES[0]
    adj = st.session_state.vxp_adjustments[base_regime]

    hdr = st.columns([0.20, 0.27, 0.27, 0.26])
    hdr[0].markdown("**Blade**")
    hdr[1].markdown("**Pitch link (turns)**")
    hdr[2].markdown("**Trim tab (mm)**")
    hdr[3].markdown("**Bolt weight (g)**")

    for b in BLADES:
        row = st.columns([0.20, 0.27, 0.27, 0.26])
        row[0].markdown(b)
        pl_v = float(row[1].number_input("", value=float(adj["pitch_turns"][b]), step=0.25, key=f"pl_all_{b}"))
        tt_v = float(row[2].number_input("", value=float(adj["trim_mm"][b]), step=0.5, key=f"tt_all_{b}"))
        wt_v = float(row[3].number_input("", value=float(adj["bolt_g"][b]), step=5.0, key=f"wt_all_{b}"))

        for rr in REGIMES:
            st.session_state.vxp_adjustments[rr]["pitch_turns"][b] = pl_v
            st.session_state.vxp_adjustments[rr]["trim_mm"][b] = tt_v
            st.session_state.vxp_adjustments[rr]["bolt_g"][b] = wt_v

    right_close_button("Close", on_click=lambda: go("mr_menu"))


def screen_solution_window():
    win_caption("SOLUTION", active=True)
    view_run = run_selector_inline(key="run_selector_solution")
    data = current_run_data(view_run)
    if not data:
        st.write("No measurements for this run yet. Go to COLLECT.")
        right_close_button("Close", on_click=lambda: go("mr_menu"))
        return

    st.selectbox("", options=["BALANCE ONLY", "TRACK ONLY", "TRACK + BALANCE"], index=2, key="sol_type")
    _centered_buttons(
        [
            ("SHOW SOLUTION", "solution_text"),
            ("Close", "mr_menu"),
        ]
    )


def screen_solution_text_window():
    win_caption("SOLUTION", active=True)
    view_run = run_selector_inline(key="run_selector_solution_text")
    data = current_run_data(view_run)
    if not data:
        st.write("No measurements for this run yet. Go to COLLECT.")
        right_close_button("Close", on_click=lambda: go("mr_menu"))
        return
    # User request: SOLUTION should be a normal report textbox (no broken
    # inline coloring). We render plain text in a disabled text_area.
    st.text_area(
        "",
        value=legacy_results_plain_text(view_run, data),
        height=380,
        key=f"solution_box_{view_run}",
        disabled=True,
        label_visibility="collapsed",
    )
    right_close_button("Close", on_click=lambda: go("mr_menu"))


def screen_next_run_window():
    run = int(st.session_state.vxp_run)
    nxt = run + 1

    win_caption("NEXT RUN", active=True)
    st.markdown(
        f"<div class='vxp-label' style='margin-top:8px;'>Current run: {run}. This simulator supports up to 3 runs.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    pad_l, mid, pad_r = st.columns([0.08, 0.84, 0.08])

    with mid:
        # Match the legacy three-action layout
        if st.button(
            f"UPDATE SETTINGS - START NEXT RUN {nxt}",
            use_container_width=True,
            disabled=(run >= 3),
            key=f"nr_update_{run}",
        ):
            st.session_state.vxp_run = nxt
            st.session_state.vxp_runs.setdefault(nxt, {})
            st.session_state.vxp_completed_by_run.setdefault(nxt, set())
            go("settings")
            st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        if st.button(
            f"NO CHANGES MADE - START NEXT RUN {nxt}",
            use_container_width=True,
            disabled=(run >= 3),
            key=f"nr_nochg_{run}",
        ):
            st.session_state.vxp_run = nxt
            st.session_state.vxp_runs.setdefault(nxt, {})
            st.session_state.vxp_completed_by_run.setdefault(nxt, set())
            go("mr_menu")
            st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        if st.button(
            f"CANCEL - STAY ON RUN {run}",
            use_container_width=True,
            key=f"nr_cancel_{run}",
        ):
            go("mr_menu")
            st.rerun()

    # Place Close at bottom-right like the legacy dialog.
    st.markdown("<div style='height:220px;'></div>", unsafe_allow_html=True)
    cols = st.columns([0.78, 0.22])
    with cols[1]:
        if st.button("Close", use_container_width=True, key=f"nr_close_{run}"):
            go("mr_menu")
            st.rerun()

def screen_aircraft_info_window():
    win_caption("AIRCRAFT INFO", active=True)
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    info = st.session_state["vxp_aircraft"]

    # Layout like the legacy dialog: labels at left, inputs centered, empty area at right.
    lab, inp, _pad = st.columns([0.30, 0.36, 0.34], gap="large")
    with lab:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("WEIGHT:")
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.markdown("C.G. :")
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.markdown("HOURS:")
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.markdown("INITIALS:")

    with inp:
        info["weight"] = float(
            st.number_input(
                "",
                value=float(info.get("weight", 0.0)),
                step=1.0,
                key="air_weight",
                label_visibility="collapsed",
            )
        )
        info["cg"] = float(
            st.number_input(
                "",
                value=float(info.get("cg", 0.0)),
                step=0.1,
                key="air_cg",
                label_visibility="collapsed",
            )
        )
        info["hours"] = float(
            st.number_input(
                "",
                value=float(info.get("hours", 0.0)),
                step=1.0,
                key="air_hours",
                label_visibility="collapsed",
            )
        )
        info["initials"] = str(
            st.text_input(
                "",
                value=str(info.get("initials", "")),
                key="air_initials",
                label_visibility="collapsed",
            )
        )

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    pad_l, mid, pad_r = st.columns([0.08, 0.84, 0.08])
    with mid:
        if st.button("Note Codes", use_container_width=True, key="air_note_codes"):
            go("note_codes")
            st.rerun()

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    right_close_button("Close", on_click=lambda: go("home"))


def screen_note_codes_window():
    win_caption("NOTE CODES", active=True)
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    # Minimal set (training / placeholder). You can extend this list later.
    codes = [
        (0, "Scheduled Insp"),
        (1, "Balance"),
        (2, "Troubleshooting"),
        (3, "Low Freq Vib"),
        (4, "Med Freq Vib"),
        (5, "High Freq Vib"),
        (6, "Component Change"),
    ]

    selected = st.session_state["vxp_note_codes"]

    # Centered list with a check column, like other VXP screens.
    pad_l, mid, pad_r = st.columns([0.10, 0.80, 0.10])
    with mid:
        for code, name in codes:
            cols = st.columns([0.84, 0.16], gap="small")
            with cols[0]:
                if st.button(f"{code:02d}  {name}", use_container_width=True, key=f"nc_btn_{code}"):
                    if code in selected:
                        selected.remove(code)
                    else:
                        selected.add(code)
                    st.rerun()
            with cols[1]:
                st.markdown(
                    f"<div style='font-size:22px; font-weight:900; padding-top:10px;'>"
                    f"{'✓' if code in selected else ''}"
                    "</div>",
                    unsafe_allow_html=True,
                )

    right_close_button("Close", on_click=lambda: go("aircraft_info"))


def screen_not_impl_window():
    win_caption("VXP", active=True)
    st.write("Solo se implementa **Main Rotor – Tracking & Balance (Option B)** para el BO105.")
    right_close_button("Close", on_click=lambda: go("home"))
