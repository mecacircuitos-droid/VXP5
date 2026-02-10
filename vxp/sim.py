import math
import random

import numpy as np

from .types import BalanceReading, Measurement

BLADES = ["BLU", "GRN", "YEL", "RED"]

# BO105 procedure set (training / simulator)
# Only these regimes exist for the BO105 in this simulator:
#  - 100% Ground
#  - Hover Flight
#  - Horizontal Flight
REGIMES = ["GROUND", "HOVER", "HORIZ"]

REGIME_LABEL = {
    "GROUND": "100% Ground",
    "HOVER": "Hover Flight",
    "HORIZ": "Horizontal Flight",
}

BLADE_CLOCK_DEG = {"YEL": 0.0, "RED": 90.0, "BLU": 180.0, "GRN": 270.0}

# BO105 — RPM de referencia en el simulador
BO105_DISPLAY_RPM = 424.0

PITCHLINK_MM_PER_TURN = 10.0
TRIMTAB_MMTRACK_PER_MM = 15.0
BOLT_IPS_PER_GRAM = 0.0020

RUN_BASE_TRACK = {
    1: {
        "GROUND": {"BLU": +6.0, "GRN": -3.0, "YEL": 0.0, "RED": -4.0},
        "HOVER": {"BLU": +7.0, "GRN": -3.5, "YEL": 0.0, "RED": -5.5},
        "HORIZ": {"BLU": +5.0, "GRN": -2.5, "YEL": 0.0, "RED": -4.0},
    },
    2: {
        "GROUND": {"BLU": +2.5, "GRN": -2.0, "YEL": 0.0, "RED": -1.0},
        "HOVER": {"BLU": +2.0, "GRN": -1.5, "YEL": 0.0, "RED": -1.0},
        "HORIZ": {"BLU": +1.8, "GRN": -1.2, "YEL": 0.0, "RED": -0.8},
    },
    3: {
        "GROUND": {"BLU": +1.5, "GRN": -1.2, "YEL": 0.0, "RED": -0.6},
        "HOVER": {"BLU": +1.2, "GRN": -1.0, "YEL": 0.0, "RED": -0.5},
        "HORIZ": {"BLU": +1.0, "GRN": -0.8, "YEL": 0.0, "RED": -0.4},
    },
}

RUN_BASE_BAL = {
    1: {"GROUND": (0.18, 125.0), "HOVER": (0.11, 110.0), "HORIZ": (0.09, 95.0)},
    2: {"GROUND": (0.14, 140.0), "HOVER": (0.08, 120.0), "HORIZ": (0.07, 105.0)},
    3: {"GROUND": (0.10, 160.0), "HOVER": (0.06, 135.0), "HORIZ": (0.05, 120.0)},
}


def default_adjustments():
    return {
        r: {
            "pitch_turns": {b: 0.0 for b in BLADES},
            "trim_mm": {b: 0.0 for b in BLADES},
            "bolt_g": {b: 0.0 for b in BLADES},
        }
        for r in REGIMES
    }


def _vec_from_clock_deg(theta_deg: float) -> np.ndarray:
    phi = math.radians(90.0 - theta_deg)
    return np.array([math.cos(phi), math.sin(phi)], dtype=float)


def _clock_deg_from_vec(v: np.ndarray) -> float:
    x, y = float(v[0]), float(v[1])
    phi = math.degrees(math.atan2(y, x))
    return (90.0 - phi) % 360.0


def simulate_measurement(run: int, regime: str, adjustments: dict) -> Measurement:
    adj = adjustments[regime]
    base_track = RUN_BASE_TRACK.get(run, RUN_BASE_TRACK[3])[regime].copy()
    base_amp, base_phase = RUN_BASE_BAL.get(run, RUN_BASE_BAL[3])[regime]

    track = {}
    for b in BLADES:
        pitch_effect = PITCHLINK_MM_PER_TURN * float(adj["pitch_turns"][b])

        trim_effect = 0.0
        # Trim tabs mainly affect the forward-flight regime in this simplified model.
        if regime == "HORIZ":
            trim_effect = TRIMTAB_MMTRACK_PER_MM * float(adj["trim_mm"][b])

        noise = random.gauss(0.0, 0.45)
        track[b] = float(base_track[b] + pitch_effect + trim_effect + noise)

    # Normalize: track is always shown relative to YEL
    yel0 = float(track["YEL"])
    for b in BLADES:
        track[b] = float(track[b] - yel0)
    track["YEL"] = 0.0

    # Simple 1/rev balance vector model
    v = _vec_from_clock_deg(base_phase) * float(base_amp)
    for b in BLADES:
        grams = float(adj["bolt_g"][b])
        v += (-BOLT_IPS_PER_GRAM * grams) * _vec_from_clock_deg(BLADE_CLOCK_DEG[b])
    v += np.array([random.gauss(0.0, 0.003), random.gauss(0.0, 0.003)], dtype=float)

    amp = float(np.linalg.norm(v))
    phase = float(_clock_deg_from_vec(v)) if amp > 1e-6 else 0.0

    return Measurement(regime=regime, balance=BalanceReading(amp, phase, BO105_DISPLAY_RPM), track_mm=track)
