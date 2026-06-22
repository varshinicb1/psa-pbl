"""
BESCOM Realistic Load Profiles.

Based on published BESCOM data:
- Peak demand: ~8,472 MW (Feb 2025, 9:50 AM IST)
- State peak: ~18,500 MW (Apr 2025)
- BESCOM share of state peak: ~46%
- Daily patterns from Karnataka load curve research
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

# Typical Bangalore daily load shape factors (hourly, normalized to peak=1.0)
# Based on published Karnataka load curve data and typical metro patterns
BANGALORE_DAILY_LOAD_CURVE: Dict[int, float] = {
    0: 0.55, 1: 0.50, 2: 0.48, 3: 0.47, 4: 0.48, 5: 0.52,
    6: 0.60, 7: 0.72, 8: 0.85, 9: 0.95, 10: 0.98, 11: 0.96,
    12: 0.88, 13: 0.82, 14: 0.80, 15: 0.82, 16: 0.85,
    17: 0.90, 18: 0.95, 19: 0.92, 20: 0.85, 21: 0.78,
    22: 0.72, 23: 0.62,
}

# Seasonal adjustment factors for Bangalore
SEASONAL_FACTORS = {
    "winter": 0.90,     # Dec-Feb (milder)
    "summer": 1.05,     # Mar-May (peak A/C load)
    "monsoon": 0.88,    # Jun-Sep (reduced load)
    "post_monsoon": 0.92,  # Oct-Nov
}

# Consumer mix for Bangalore (BESCOM data)
CONSUMER_MIX = {
    "residential": 0.48,
    "commercial": 0.22,
    "industrial": 0.15,
    "agricultural": 0.03,
    "public": 0.07,
    "others": 0.05,
}

# Load pattern shapes per consumer type (hourly factors)
INDUSTRIAL_LOAD_PATTERN: Dict[int, float] = {
    0: 0.45, 1: 0.40, 2: 0.38, 3: 0.38, 4: 0.40, 5: 0.50,
    6: 0.65, 7: 0.85, 8: 0.95, 9: 1.00, 10: 0.98, 11: 0.95,
    12: 0.78, 13: 0.72, 14: 0.65, 15: 0.68, 16: 0.75,
    17: 0.82, 18: 0.72, 19: 0.60, 20: 0.55, 21: 0.50,
    22: 0.48, 23: 0.46,
}

RESIDENTIAL_LOAD_PATTERN: Dict[int, float] = {
    0: 0.55, 1: 0.48, 2: 0.44, 3: 0.42, 4: 0.44, 5: 0.52,
    6: 0.58, 7: 0.70, 8: 0.62, 9: 0.55, 10: 0.52, 11: 0.50,
    12: 0.48, 13: 0.45, 14: 0.48, 15: 0.55, 16: 0.62,
    17: 0.72, 18: 0.85, 19: 0.95, 20: 1.00, 21: 0.95,
    22: 0.85, 23: 0.70,
}

COMMERCIAL_LOAD_PATTERN: Dict[int, float] = {
    0: 0.25, 1: 0.20, 2: 0.18, 3: 0.18, 4: 0.20, 5: 0.30,
    6: 0.50, 7: 0.72, 8: 0.88, 9: 0.95, 10: 0.98, 11: 1.00,
    12: 0.92, 13: 0.88, 14: 0.85, 15: 0.88, 16: 0.92,
    17: 0.85, 18: 0.72, 19: 0.60, 20: 0.50, 21: 0.42,
    22: 0.35, 23: 0.30,
}


@dataclass
class BESCOMLoadProfile:
    """Real-time load profile generator for BESCOM grid."""

    peak_mw: float = 8472.0
    base_year: int = 2025
    noise_std: float = 0.02

    def get_season(self, month: int) -> str:
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "summer"
        elif month in [6, 7, 8, 9]:
            return "monsoon"
        else:
            return "post_monsoon"

    def get_hourly_factor(self, dt: datetime) -> float:
        """Get the normalized load factor for a given datetime (0.0-1.0)."""
        hour = dt.hour
        month = dt.month
        is_weekend = dt.weekday() >= 5

        base_factor = BANGALORE_DAILY_LOAD_CURVE.get(hour, 0.7)
        seasonal = SEASONAL_FACTORS.get(self.get_season(month), 1.0)

        # Weekend reduction
        weekend_factor = 0.88 if is_weekend else 1.0

        # Add noise
        noise = random.gauss(0, self.noise_std)

        factor = base_factor * seasonal * weekend_factor + noise
        return max(0.3, min(1.0, factor))

    def get_current_load_mw(self, dt: Optional[datetime] = None) -> float:
        """Get the current total BESCOM load in MW."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        factor = self.get_hourly_factor(dt)
        return self.peak_mw * factor

    def get_load_by_zone(
        self, zone_loads: Dict[str, float], dt: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get load breakdown by zone/category."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        factor = self.get_hourly_factor(dt)
        return {zone: base * factor for zone, base in zone_loads.items()}


def get_bangalore_daily_load_curve(hour: int) -> float:
    """Get the normalized load factor for a given hour (0-23)."""
    return BANGALORE_DAILY_LOAD_CURVE.get(hour % 24, 0.7)


def generate_bescom_loads(
    net,
    peak_mw: float = 8472.0,
    dt: Optional[datetime] = None,
    noise_std: float = 0.02,
) -> None:
    """
    Set loads on a BESCOM pandapower network based on time of day.

    Distributes the total BESCOM load across all load buses proportional
    to their rated capacity, with time-of-day variation.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    profile = BESCOMLoadProfile(peak_mw=peak_mw, noise_std=noise_std)
    load_factor = profile.get_hourly_factor(dt)
    current_load = peak_mw * load_factor

    total_rated = net.load.p_mw.sum()
    if total_rated <= 0:
        return

    scale = current_load / total_rated
    net.load.scaling = scale
