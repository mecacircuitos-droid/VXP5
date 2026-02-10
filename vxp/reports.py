from __future__ import annotations

from typing import Dict, List, Tuple
import re

from .types import Measurement
from .solver import suggest_pitchlink, suggest_trimtabs, suggest_weight

BLADES = ["BLU", "GRN", "YEL", "RED"]

# Blade colors (approximate legacy VXP palette)
BLADE_COLOR = {
    "BLU": "#0000cc",
    "GRN": "#008800",
    "YEL": "#b09000",
    "RED": "#cc0000",
}

# Subtle coloring for regime names (legacy screens used colored regime text)
REGIME_COLOR = {
    "GROUND": "#000000",
    "HOVER": "#0000cc",
    "HORIZ": "#008800",
}


def _c(txt: str, color: str) -> str:
    """Wrap text in a color span. Safe for use inside vxp-mono (white-space:pre)."""

    return f"<span style='color:{color};'>{txt}</span>"


# Display order (BO105 procedure): ONLY these three.
DISPLAY_POINTS: List[Tuple[str, str]] = [
    ("100% Ground", "GROUND"),
    ("Hover Flight", "HOVER"),
    ("Horizontal Flight", "HORIZ"),
]


def clock_label(theta_deg: float) -> str:
    """Convert phase degrees to a 12-hour clock label (legacy VXP style)."""

    hour = int(round(theta_deg / 30.0)) % 12
    hour = 12 if hour == 0 else hour
    minute = 0 if abs((theta_deg / 30.0) - round(theta_deg / 30.0)) < 0.25 else 30
    return f"{hour:02d}:{minute:02d}"


def legacy_results_text(run: int, meas_by_regime: Dict[str, Measurement]) -> str:
    """Legacy-like mono report used on MEASUREMENTS GRAPH / LIST.

    - BO105 only (Ground / Hover / Horizontal)
    - Adds blade & regime color cues
    - Aligns Adjustments so values appear directly under each blade
    """

    lines: List[str] = []
    lines.append("BO105   MAIN ROTOR   TRACK & BALANCE")
    lines.append("OPTION: B   STROBEX MODE: B")
    lines.append(f"RUN: {run}   ID: TRAINING")
    lines.append("")

    # -------------------------
    # Balance measurements
    # -------------------------
    lines.append("----- Balance Measurements -----")
    for name, src in DISPLAY_POINTS:
        if src not in meas_by_regime:
            continue
        m = meas_by_regime[src]
        amp = float(m.balance.amp_ips)
        ph = float(m.balance.phase_deg)
        reg = _c(f"{name:<18}", REGIME_COLOR.get(src, "#000"))
        lines.append(f"{reg}  1P {amp:0.2f} IPS  {clock_label(ph):>5}  RPM:{m.balance.rpm:0.0f}")

    lines.append("")

    # -------------------------
    # Track height
    # -------------------------
    lines.append("----- Track Height (mm rel. YEL) -----")
    for name, src in DISPLAY_POINTS:
        if src not in meas_by_regime:
            continue
        m = meas_by_regime[src]
        reg = _c(f"{name:<18}", REGIME_COLOR.get(src, "#000"))
        parts = [_c(f"{b}:{m.track_mm[b]:+5.1f}", BLADE_COLOR[b]) for b in BLADES]
        lines.append(f"{reg}  " + "  ".join(parts))

    # -------------------------
    # Solution / Prediction
    # -------------------------
    lines.append("")
    lines.append("----- Solution Options -----")

    used_regimes = [name for name, src in DISPLAY_POINTS if src in meas_by_regime]
    if not used_regimes:
        lines.append("(No regimes collected yet)")
        lines.append("")
        return "\n".join(lines)

    lines.append("SOLUTION TYPE: BALANCE")
    lines.append(f"REGIMES USED: {', '.join(used_regimes)}")
    lines.append("USED: Pitch link, Trim tab, Weight")

    pl = suggest_pitchlink(meas_by_regime)
    tt = suggest_trimtabs(meas_by_regime)
    wb, wg = suggest_weight(meas_by_regime)

    lines.append("")
    lines.append("Adjustments")

    # Header aligned like the original (values appear directly under each blade).
    # We use fixed-width columns so the result is stable even with inline <span> coloring.
    COL_W = 8

    def _hblade(b: str) -> str:
        return _c(f"{b:>{COL_W}}", BLADE_COLOR[b])

    def _vblade(b: str, s: str) -> str:
        return _c(f"{s:>{COL_W}}", BLADE_COLOR[b])

    def _hdr(label: str) -> str:
        return f"{label:<12}" + _hblade("BLU") + _hblade("GRN") + _hblade("YEL") + _hblade("RED")

    def _row(label: str, vals: Dict[str, float], fmt: str) -> str:
        return (
            f"{label:<12}"
            + _vblade("BLU", format(vals["BLU"], fmt))
            + _vblade("GRN", format(vals["GRN"], fmt))
            + _vblade("YEL", format(vals["YEL"], fmt))
            + _vblade("RED", format(vals["RED"], fmt))
        )

    # P/L
    lines.append(_hdr("P/L(flats)"))
    lines.append(_row("", pl, "6.2f"))

    # Keep the same names as the legacy screen (TabS5/TabS6)
    lines.append(_hdr("TabS5(deg)"))
    lines.append(_row("", {b: tt[b] * 0.8 for b in BLADES}, "6.1f"))
    lines.append(_hdr("TabS6(deg)"))
    lines.append(_row("", {b: tt[b] * 0.8 for b in BLADES}, "6.1f"))

    # Weight (only one blade gets the suggested grams)
    wrow = {b: 0.0 for b in BLADES}
    wrow[wb] = float(wg)
    lines.append(_hdr("Wt(plqts)"))
    lines.append(_row("", wrow, "6.0f"))

    lines.append("")
    lines.append("----- Prediction -----")
    for name, src in DISPLAY_POINTS:
        if src not in meas_by_regime:
            continue
        m = meas_by_regime[src]
        reg = _c(f"{name:<18}", REGIME_COLOR.get(src, "#000"))
        lines.append(f"{reg}  M/R L   {m.balance.amp_ips:0.2f}")

    lines.append("Track Split")
    for name, src in DISPLAY_POINTS:
        if src not in meas_by_regime:
            continue
        m = meas_by_regime[src]
        vals = [m.track_mm[b] for b in BLADES]
        split = max(vals) - min(vals)
        reg = _c(f"{name:<18}", REGIME_COLOR.get(src, "#000"))
        lines.append(f"{reg}  {split:0.2f}")

    lines.append("")
    return "\n".join(lines)


def legacy_results_plain_text(run: int, meas_by_regime: Dict[str, Measurement]) -> str:
    """Same report as legacy_results_text but without HTML tags.

    Useful for rendering inside Streamlit widgets like st.text_area where we
    want a 'normal' textbox and reliable monospace alignment.
    """

    txt = legacy_results_text(run, meas_by_regime)
    # Remove the inline <span ...> color wrappers.
    return re.sub(r"</?span[^>]*>", "", txt)


def legacy_results_html(run: int, meas_by_regime: Dict[str, Measurement]) -> str:
    """HTML report used in the UI.

    Streamlit + HTML can sometimes collapse whitespace when inline spans are
    present. For the *Adjustments* block we therefore render a real HTML table
    with fixed column widths (so BLU/GRN/YEL/RED always line up).
    """

    # Build the classic mono text (with colored regime labels). We'll reuse it
    # for everything except the Adjustments block.
    txt = legacy_results_text(run, meas_by_regime)

    # Split the report around the first "Adjustments" marker.
    marker = "\nAdjustments\n"
    if marker not in txt:
        # Fallback: just render as-is.
        return (
            "<div class='vxp-mono' style='white-space:pre; height:560px; overflow:auto;'>"
            + txt
            + "</div>"
        )

    before, after = txt.split(marker, 1)

    # Recompute adjustments to render as a stable table.
    pl = suggest_pitchlink(meas_by_regime)
    tt = suggest_trimtabs(meas_by_regime)
    wb, wg = suggest_weight(meas_by_regime)
    wrow = {b: 0.0 for b in BLADES}
    wrow[wb] = float(wg)

    def td(text: str, *, color: str | None = None, bold: bool = False, w: int = 86) -> str:
        style = [f"width:{w}px", "padding:2px 8px", "text-align:right", "white-space:pre"]
        if color:
            style.append(f"color:{color}")
        if bold:
            style.append("font-weight:700")
        return f"<td style='{';'.join(style)}'>{text}</td>"

    def th(text: str, color: str) -> str:
        return td(text, color=color, bold=True)

    def row(label: str, vals: Dict[str, float], fmt: str) -> str:
        return (
            "<tr>"
            + f"<td style='width:140px; padding:2px 8px; text-align:left; white-space:pre; font-weight:700'>{label}</td>"
            + td(format(vals['BLU'], fmt), color=BLADE_COLOR['BLU'])
            + td(format(vals['GRN'], fmt), color=BLADE_COLOR['GRN'])
            + td(format(vals['YEL'], fmt), color=BLADE_COLOR['YEL'])
            + td(format(vals['RED'], fmt), color=BLADE_COLOR['RED'])
            + "</tr>"
        )

    table = (
        "<div style='margin-top:6px; margin-bottom:6px; font-weight:700;'>Adjustments</div>"
        "<table style='border-collapse:collapse; font-family:Courier New,Consolas,monospace; font-size:14px;'>"
        "<tr>"
        "<td style='width:140px; padding:2px 8px; text-align:left; white-space:pre; font-weight:700'></td>"
        + th("BLU", BLADE_COLOR["BLU"])
        + th("GRN", BLADE_COLOR["GRN"])
        + th("YEL", BLADE_COLOR["YEL"])
        + th("RED", BLADE_COLOR["RED"])
        + "</tr>"
        + row("P/L(flats)", pl, "6.2f")
        + row("TabS5(deg)", {b: tt[b] * 0.8 for b in BLADES}, "6.1f")
        + row("TabS6(deg)", {b: tt[b] * 0.8 for b in BLADES}, "6.1f")
        + row("Wt(plqts)", wrow, "6.0f")
        + "</table>"
    )

    # Remove the old adjustments lines from `after` (up to the Prediction header).
    if "\n----- Prediction -----\n" in after:
        _old_adj, rest = after.split("\n----- Prediction -----\n", 1)
        after = "----- Prediction -----\n" + rest

    return (
        "<div class='vxp-mono' style='white-space:normal; height:560px; overflow:auto;'>"
        + f"<div style='white-space:pre'>{before}</div>"
        + table
        + f"<div style='white-space:pre; margin-top:8px'>{after}</div>"
        + "</div>"
    )
