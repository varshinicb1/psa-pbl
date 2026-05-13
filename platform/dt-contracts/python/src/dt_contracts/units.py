from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaseValues:
    """Base values for per-unit conversions."""

    base_mva: float
    base_kv: float


def kw_to_mw(p_kw: float) -> float:
    return p_kw / 1000.0


def mw_to_kw(p_mw: float) -> float:
    return p_mw * 1000.0


def kvar_to_mvar(q_kvar: float) -> float:
    return q_kvar / 1000.0


def mvar_to_kvar(q_mvar: float) -> float:
    return q_mvar * 1000.0


def mw_to_pu(p_mw: float, base_mva: float) -> float:
    return p_mw / base_mva


def pu_to_mw(p_pu: float, base_mva: float) -> float:
    return p_pu * base_mva

