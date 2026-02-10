from dataclasses import dataclass
from typing import Dict

@dataclass
class BalanceReading:
    amp_ips: float
    phase_deg: float
    rpm: float

@dataclass
class Measurement:
    regime: str
    balance: BalanceReading
    track_mm: Dict[str, float]  # BLU/GRN/YEL/RED relative to YEL
