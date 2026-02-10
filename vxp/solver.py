import math
from typing import Dict, Tuple

from .types import Measurement

BLADES = ["BLU", "GRN", "YEL", "RED"]

# Keep in sync with vxp.sim.REGIMES
REGIMES = ["GROUND", "HOVER", "HORIZ"]

BLADE_CLOCK_DEG = {"YEL": 0.0, "RED": 90.0, "BLU": 180.0, "GRN": 270.0}

PITCHLINK_MM_PER_TURN = 10.0
TRIMTAB_MMTRACK_PER_MM = 15.0
BOLT_IPS_PER_GRAM = 0.0020


def track_limit(regime: str) -> float:
    # Ground run is more permissive; hover and horizontal are tighter.
    return 15.0


def balance_limit(regime: str) -> float:
    return 0.20 if regime == "GROUND" else 0.15


# -----------------------------
# Legacy-style limit bands (for UI icons)
# -----------------------------
# The original VXP shows four different symbols after each regime is collected:
#  - Black check mark: measurement taken, but no limits defined.
#  - Green check mark: within acceptance limits.
#  - Green exclamation: exceeds acceptance limits.
#  - Red stop sign: exceeds procedural limits (action required before continuing).
#
# For the BO105 training simulator we implement a pragmatic, two-band model:
#   acceptance_limit < procedural_limit
#
# These values are chosen to be consistent with typical track & balance workflows
# (tight acceptance band, wider “do-not-proceed” band).


def acceptance_track_limit(regime: str) -> float:
    # BO105 training acceptance band.
    # Base simulated track spreads are ~8–14 mm; keep most runs in OK.
    return 20.0


def procedural_track_limit(regime: str) -> float:
    # Allowable spread before it's considered unsafe to proceed.
    # Forward-flight tracking in many procedures mentions 50 mm as a hard boundary.
    return 30.0


def acceptance_balance_limit(regime: str) -> float:
    # BO105 training acceptance band. Keep most simulated values in OK.
    return 0.20


def procedural_balance_limit(regime: str) -> float:
    # Procedural (hard) band; must remain above acceptance.
    return 0.30


def regime_status(regime: str, m: Measurement | None) -> str | None:
    """Return a status code for a regime.

    None: no measurement
    "OK": within acceptance
    "WARN": exceeds acceptance but within procedural
    "STOP": exceeds procedural
    "DONE": measurement exists but no limits
    """
    if m is None:
        return None

    try:
        ts = track_spread(m)
        amp = float(m.balance.amp_ips)
    except Exception:
        return "DONE"

    # If limits are not defined for some reason, fall back to legacy “DONE”.
    if regime not in REGIMES:
        return "DONE"

    if ts > procedural_track_limit(regime) or amp > procedural_balance_limit(regime):
        return "STOP"
    if ts > acceptance_track_limit(regime) or amp > acceptance_balance_limit(regime):
        return "WARN"
    return "OK"


def track_spread(m: Measurement) -> float:
    vals = [m.track_mm[b] for b in BLADES]
    return float(max(vals) - min(vals))


def all_ok(meas_by_regime: Dict[str, Measurement]) -> bool:
    for r in REGIMES:
        if r not in meas_by_regime:
            return False
        if track_spread(meas_by_regime[r]) > track_limit(r):
            return False
        if meas_by_regime[r].balance.amp_ips > balance_limit(r):
            return False
    return True


def _round_quarter(x: float) -> float:
    return round(x * 4.0) / 4.0


def suggest_pitchlink(meas: Dict[str, Measurement]) -> Dict[str, float]:
    # Primary pitch-link adjustment is based on ground + hover.
    used = [r for r in ("GROUND", "HOVER") if r in meas]
    if not used:
        return {b: 0.0 for b in BLADES}
    out = {}
    for b in BLADES:
        avg = sum(meas[r].track_mm[b] for r in used) / len(used)
        out[b] = _round_quarter((-avg) / PITCHLINK_MM_PER_TURN)
    return out


def suggest_trimtabs(meas: Dict[str, Measurement]) -> Dict[str, float]:
    """Suggest trim-tab bending based on Horizontal Flight.

    In this simplified BO105 workflow, Horizontal Flight is the only
    forward-flight regime.
    """
    if "HORIZ" not in meas:
        return {b: 0.0 for b in BLADES}
    out = {}
    for b in BLADES:
        dev = meas["HORIZ"].track_mm[b]
        out[b] = max(-5.0, min(5.0, _round_quarter((-dev) / TRIMTAB_MMTRACK_PER_MM)))
    return out


def suggest_weight(meas: Dict[str, Measurement]) -> Tuple[str, float]:
    if not meas:
        return ("YEL", 0.0)

    worst_r = max(meas.keys(), key=lambda r: meas[r].balance.amp_ips)
    m = meas[worst_r]
    amp = m.balance.amp_ips
    phase = m.balance.phase_deg
    target = (phase + 180.0) % 360.0

    def dist(a, b):
        d = abs(a - b) % 360.0
        return min(d, 360.0 - d)

    blade = min(BLADES, key=lambda bb: dist(target, BLADE_CLOCK_DEG[bb]))
    grams = max(5.0, min(120.0, round(amp / BOLT_IPS_PER_GRAM / 5.0) * 5.0))
    return blade, grams
