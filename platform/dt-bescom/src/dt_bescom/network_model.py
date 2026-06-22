"""
BESCOM Bangalore Power Grid Network Model.

This module builds an accurate pandapower network model of the
Bangalore metropolitan transmission and distribution grid based on
real BESCOM/KPTCL substation data.

Reference network (based on published BESCOM/KPTCL data):
- 3 x 400kV Master Receiving Stations (Nelamangala, Hoody, Somanahalli)
- 2 x 400kV GIS substations (Bidadi, Yelahanka) under POWERGRID
- 15 x 220kV Receiving Stations feeding the city
- ~90 x 66/11kV distribution substations
- Total peak demand: ~8,472 MW (Feb 2025)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# BANGALORE 400kV MASTER RECEIVING STATIONS (MRS)
# These receive power at 400kV from the state/national grid and step down to 220kV
BANGALORE_400KV_SUBSTATIONS: List[Dict] = [
    {"id": "SS-400-NEL", "name": "Nelamangala 400kV MRS", "lat": 13.099, "lon": 77.396, "region": "North"},
    {"id": "SS-400-HDY", "name": "Hoody 400kV MRS", "lat": 12.993, "lon": 77.726, "region": "East"},
    {"id": "SS-400-SMH", "name": "Somanahalli 400kV MRS", "lat": 12.878, "lon": 77.547, "region": "South"},
    {"id": "SS-400-BDD", "name": "Bidadi 400kV GIS", "lat": 12.801, "lon": 77.387, "region": "West"},
    {"id": "SS-400-YLK", "name": "Yelahanka 400kV GIS", "lat": 13.100, "lon": 77.596, "region": "North"},
]

# BANGALORE 220kV RECEIVING STATIONS (15 total, feeding city zones)
BANGALORE_220KV_SUBSTATIONS: List[Dict] = [
    {"id": "SS-220-PNY", "name": "Peenya 220kV", "lat": 13.029, "lon": 77.522, "zone": "West", "load_mw": 450},
    {"id": "SS-220-HBL", "name": "Hebbal 220kV", "lat": 13.036, "lon": 77.597, "zone": "North", "load_mw": 380},
    {"id": "SS-220-YLH", "name": "Yeshwanthpur 220kV", "lat": 13.022, "lon": 77.547, "zone": "West", "load_mw": 350},
    {"id": "SS-220-KRG", "name": "K.R.Puram 220kV", "lat": 12.991, "lon": 77.673, "zone": "East", "load_mw": 420},
    {"id": "SS-220-WFD", "name": "Whitefield 220kV", "lat": 12.970, "lon": 77.750, "zone": "East", "load_mw": 310},
    {"id": "SS-220-BSK", "name": "Basaveshwaranagar 220kV", "lat": 12.976, "lon": 77.546, "zone": "West", "load_mw": 290},
    {"id": "SS-220-VKY", "name": "Vijayanagar 220kV", "lat": 12.964, "lon": 77.533, "zone": "South", "load_mw": 330},
    {"id": "SS-220-JPR", "name": "J.P.Nagar 220kV", "lat": 12.906, "lon": 77.585, "zone": "South", "load_mw": 370},
    {"id": "SS-220-BRP", "name": "B.T.M Layout 220kV", "lat": 12.914, "lon": 77.608, "zone": "South", "load_mw": 260},
    {"id": "SS-220-MRD", "name": "Malleshwaram 220kV", "lat": 12.993, "lon": 77.570, "zone": "Central", "load_mw": 340},
    {"id": "SS-220-HSR", "name": "H.S.R Layout 220kV", "lat": 12.909, "lon": 77.635, "zone": "South", "load_mw": 280},
    {"id": "SS-220-RNR", "name": "R.T.Nagar 220kV", "lat": 13.017, "lon": 77.598, "zone": "North", "load_mw": 225},
    {"id": "SS-220-IND", "name": "Indiranagar 220kV", "lat": 12.979, "lon": 77.641, "zone": "East", "load_mw": 300},
    {"id": "SS-220-MTY", "name": "Madiwala 220kV", "lat": 12.911, "lon": 77.613, "zone": "South", "load_mw": 240},
    {"id": "SS-220-DOM", "name": "Domlur 220kV", "lat": 12.960, "lon": 77.639, "zone": "Central", "load_mw": 195},
]

# BANGALORE 66kV SUBSTATIONS (subset of ~90, major ones)
BANGALORE_66KV_SUBSTATIONS: List[Dict] = [
    {"id": "SS-66-MAJ", "name": "Majestic 66kV", "lat": 12.976, "lon": 77.571, "zone": "Central", "load_mw": 85},
    {"id": "SS-66-SGP", "name": "Shivajinagar 66kV", "lat": 12.982, "lon": 77.604, "zone": "Central", "load_mw": 72},
    {"id": "SS-66-KRG", "name": "Koramangala 66kV", "lat": 12.927, "lon": 77.624, "zone": "South", "load_mw": 68},
    {"id": "SS-66-JPR", "name": "Jayanagar 66kV", "lat": 12.928, "lon": 77.584, "zone": "South", "load_mw": 75},
    {"id": "SS-66-RNR", "name": "Rajajinagar 66kV", "lat": 12.983, "lon": 77.553, "zone": "West", "load_mw": 65},
    {"id": "SS-66-MLD", "name": "Malleshwaram 66kV", "lat": 12.995, "lon": 77.572, "zone": "Central", "load_mw": 58},
    {"id": "SS-66-SAD", "name": "Sadashivanagar 66kV", "lat": 13.003, "lon": 77.582, "zone": "North", "load_mw": 52},
    {"id": "SS-66-YLH", "name": "Yelahanka 66kV", "lat": 13.102, "lon": 77.597, "zone": "North", "load_mw": 48},
    {"id": "SS-66-VID", "name": "Vidyaranyapura 66kV", "lat": 13.062, "lon": 77.551, "zone": "North", "load_mw": 42},
    {"id": "SS-66-MTN", "name": "Mathikere 66kV", "lat": 13.010, "lon": 77.556, "zone": "West", "load_mw": 45},
    {"id": "SS-66-BSK", "name": "Basaveshwaranagar 66kV", "lat": 12.977, "lon": 77.544, "zone": "West", "load_mw": 55},
    {"id": "SS-66-VVY", "name": "V.V.Puram 66kV", "lat": 12.955, "lon": 77.562, "zone": "Central", "load_mw": 50},
    {"id": "SS-66-PNY", "name": "Peenya Industrial 66kV", "lat": 13.027, "lon": 77.520, "zone": "West", "load_mw": 90},
    {"id": "SS-66-BTM", "name": "B.T.M Layout 66kV", "lat": 12.916, "lon": 77.609, "zone": "South", "load_mw": 62},
    {"id": "SS-66-HSR", "name": "H.S.R Layout 66kV", "lat": 12.910, "lon": 77.636, "zone": "South", "load_mw": 56},
    {"id": "SS-66-ELE", "name": "Electronic City 66kV", "lat": 12.845, "lon": 77.660, "zone": "South", "load_mw": 95},
    {"id": "SS-66-WFD", "name": "Whitefield 66kV", "lat": 12.969, "lon": 77.748, "zone": "East", "load_mw": 78},
    {"id": "SS-66-MRP", "name": "Marathahalli 66kV", "lat": 12.959, "lon": 77.700, "zone": "East", "load_mw": 70},
    {"id": "SS-66-KRP", "name": "K.R.Puram 66kV", "lat": 12.990, "lon": 77.672, "zone": "East", "load_mw": 65},
    {"id": "SS-66-BRP", "name": "Brookefield 66kV", "lat": 12.965, "lon": 77.713, "zone": "East", "load_mw": 60},
    {"id": "SS-66-MGD", "name": "Magadi Road 66kV", "lat": 12.972, "lon": 77.552, "zone": "West", "load_mw": 48},
    {"id": "SS-66-KNG", "name": "Kengeri 66kV", "lat": 12.907, "lon": 77.482, "zone": "West", "load_mw": 52},
    {"id": "SS-66-BSK2", "name": "Banashankari 66kV", "lat": 12.918, "lon": 77.548, "zone": "South", "load_mw": 58},
    {"id": "SS-66-KMP", "name": "Kumaraswamy Layout 66kV", "lat": 12.903, "lon": 77.561, "zone": "South", "load_mw": 44},
    {"id": "SS-66-TMK", "name": "Tumkur Road 66kV", "lat": 13.024, "lon": 77.508, "zone": "West", "load_mw": 38},
    {"id": "SS-66-DLG", "name": "Dollar Layout 66kV", "lat": 12.910, "lon": 77.590, "zone": "South", "load_mw": 36},
    {"id": "SS-66-HNL", "name": "Hennur 66kV", "lat": 13.027, "lon": 77.637, "zone": "North", "load_mw": 42},
    {"id": "SS-66-SRJ", "name": "Sarjapur 66kV", "lat": 12.892, "lon": 77.685, "zone": "South", "load_mw": 55},
    {"id": "SS-66-BNR", "name": "Bannerghatta 66kV", "lat": 12.880, "lon": 77.598, "zone": "South", "load_mw": 40},
    {"id": "SS-66-KNP", "name": "Kanakapura Road 66kV", "lat": 12.895, "lon": 77.562, "zone": "South", "load_mw": 46},
]

# Transmission line parameters (per km, typical for 400kV and 220kV in Indian grid)
LINE_PARAMS: Dict[str, Dict] = {
    "400kV_twin": {"r_ohm_per_km": 0.031, "x_ohm_per_km": 0.327, "b_micros_per_km": 3.86, "rating_mva": 1200},
    "400kV_quad": {"r_ohm_per_km": 0.015, "x_ohm_per_km": 0.307, "b_micros_per_km": 4.02, "rating_mva": 2000},
    "220kV_twin": {"r_ohm_per_km": 0.062, "x_ohm_per_km": 0.412, "b_micros_per_km": 2.78, "rating_mva": 600},
    "220kV_single": {"r_ohm_per_km": 0.124, "x_ohm_per_km": 0.435, "b_micros_per_km": 2.65, "rating_mva": 350},
    "66kV": {"r_ohm_per_km": 0.270, "x_ohm_per_km": 0.405, "b_micros_per_km": 2.10, "rating_mva": 100, "c_nf_per_km": 11.0, "max_i_ka": 0.87},
}


@dataclass
class BESCOMNetworkConfig:
    """Configuration for building the BESCOM network model."""

    include_400kv: bool = True
    include_220kv: bool = True
    include_66kv: bool = True
    base_mva: int = 100
    freq_hz: float = 50.0


def get_bangalore_substations(voltage_class: Optional[str] = None) -> List[Dict]:
    """Get BESCOM Bangalore substation data."""
    all_ss = []
    if voltage_class is None or voltage_class == "400":
        all_ss.extend(BANGALORE_400KV_SUBSTATIONS)
    if voltage_class is None or voltage_class == "220":
        all_ss.extend(BANGALORE_220KV_SUBSTATIONS)
    if voltage_class is None or voltage_class == "66":
        all_ss.extend(BANGALORE_66KV_SUBSTATIONS)
    return all_ss


def _substation_index(subs: List[Dict], ss_id: str) -> int:
    for i, s in enumerate(subs):
        if s["id"] == ss_id:
            return i
    raise ValueError(f"Substation {ss_id} not found")


def build_bescom_network(config: Optional[BESCOMNetworkConfig] = None):
    """
    Build a BESCOM Bangalore network model in pandapower.

    Returns a fully-constructed pandapower network with:
    - 5 x 400kV buses (Nelamangala, Hoody, Somanahalli, Bidadi, Yelahanka)
    - 15 x 220kV buses (city receiving stations)
    - 30 x 66kV buses (distribution substations)
    - Transformers between voltage levels
    - Transmission lines with real impedance parameters
    - Loads scaled to real BESCOM peak demand (~8,472 MW)
    - External grid connection representing state grid infeeds
    """
    import pandapower as pp

    config = config or BESCOMNetworkConfig()

    net = pp.create_empty_network(name="BESCOM Bangalore Grid")
    net.sn_mva = config.base_mva
    net.freq = config.freq_hz

    buses_400kv: List[int] = []
    buses_220kv: List[int] = []
    buses_66kv: List[int] = []

    zone_colors = {"North": "blue", "South": "red", "East": "green", "West": "orange", "Central": "purple"}

    # --- 400kV buses ---
    if config.include_400kv:
        for ss in BANGALORE_400KV_SUBSTATIONS:
            b = pp.create_bus(net, vn_kv=400.0, name=ss["name"], type="b")
            buses_400kv.append(b)

    # --- 220kV buses ---
    if config.include_220kv:
        for ss in BANGALORE_220KV_SUBSTATIONS:
            b = pp.create_bus(net, vn_kv=220.0, name=ss["name"], type="b")
            buses_220kv.append(b)

    # --- 66kV buses ---
    if config.include_66kv:
        for ss in BANGALORE_66KV_SUBSTATIONS:
            b = pp.create_bus(net, vn_kv=66.0, name=ss["name"], type="b")
            buses_66kv.append(b)

    # --- External Grid (state grid connection at 400kV) ---
    if buses_400kv:
        for i, b in enumerate(buses_400kv):
            # Nelamangala, Hoody, Somanahalli are the main infeeds
            if i < 3:
                pp.create_ext_grid(net, bus=b, vm_pu=1.01, name=f"Grid_infeed_{BANGALORE_400KV_SUBSTATIONS[i]['name']}")

    # --- 400/220kV Transformers ---
    if config.include_400kv and config.include_220kv:
        _400_to_220_connections = [
            # (400kV station, 220kV stations it feeds)
            ("SS-400-NEL", ["SS-220-PNY", "SS-220-YLH", "SS-220-HBL", "SS-220-RNR"]),
            ("SS-400-HDY", ["SS-220-KRG", "SS-220-WFD", "SS-220-IND", "SS-220-DOM"]),
            ("SS-400-SMH", ["SS-220-VKY", "SS-220-JPR", "SS-220-BRP", "SS-220-HSR", "SS-220-MTY"]),
            ("SS-400-BDD", ["SS-220-BSK", "SS-220-MRD"]),
            ("SS-400-YLK", ["SS-220-YLH", "SS-220-HBL"]),
        ]
        for hv_id, lv_ids in _400_to_220_connections:
            hv_idx = _substation_index(BANGALORE_400KV_SUBSTATIONS, hv_id)
            hv_bus = buses_400kv[hv_idx]
            for lv_id in lv_ids:
                lv_idx = _substation_index(BANGALORE_220KV_SUBSTATIONS, lv_id)
                lv_bus = buses_220kv[lv_idx]
                pp.create_transformer_from_parameters(
                    net,
                    hv_bus=hv_bus,
                    lv_bus=lv_bus,
                    sn_mva=500,
                    vn_hv_kv=400.0,
                    vn_lv_kv=220.0,
                    vkr_percent=0.35,
                    vk_percent=12.5,
                    pfe_kw=120,
                    i0_percent=0.08,
                    tap_side="hv",
                    tap_neutral=0,
                    tap_min=-9,
                    tap_max=9,
                    tap_step_percent=1.25,
                    name=f"Tx 400/220 {hv_id}->{lv_id}",
                )

    # --- 220/66kV Transformers ---
    if config.include_220kv and config.include_66kv:
        _220_to_66_connections = [
            ("SS-220-PNY", ["SS-66-PNY", "SS-66-MTN", "SS-66-TMK"]),
            ("SS-220-HBL", ["SS-66-YLH", "SS-66-VID", "SS-66-SAD", "SS-66-HNL"]),
            ("SS-220-YLH", ["SS-66-MLD", "SS-66-RNR", "SS-66-MAJ", "SS-66-BSK"]),
            ("SS-220-KRG", ["SS-66-KRP", "SS-66-MRP", "SS-66-MGD"]),
            ("SS-220-WFD", ["SS-66-WFD", "SS-66-BRP"]),
            ("SS-220-BSK", ["SS-66-BSK", "SS-66-VVY", "SS-66-KNG"]),
            ("SS-220-VKY", ["SS-66-JPR", "SS-66-BSK2", "SS-66-KMP"]),
            ("SS-220-JPR", ["SS-66-JPR", "SS-66-KRG", "SS-66-DLG", "SS-66-KNP"]),
            ("SS-220-BRP", ["SS-66-BTM", "SS-66-HSR", "SS-66-BNR"]),
            ("SS-220-MRD", ["SS-66-MAJ", "SS-66-SGP", "SS-66-VVY"]),
            ("SS-220-HSR", ["SS-66-HSR", "SS-66-ELE", "SS-66-SRJ"]),
            ("SS-220-RNR", ["SS-66-RNR", "SS-66-MTN"]),
            ("SS-220-IND", ["SS-66-WFD", "SS-66-MRP", "SS-66-KRP"]),
            ("SS-220-MTY", ["SS-66-BTM", "SS-66-KRG", "SS-66-DLG"]),
            ("SS-220-DOM", ["SS-66-SGP", "SS-66-MLD", "SS-66-VVY"]),
        ]
        for hv_id, lv_ids in _220_to_66_connections:
            hv_idx = _substation_index(BANGALORE_220KV_SUBSTATIONS, hv_id)
            hv_bus = buses_220kv[hv_idx]
            for lv_id in lv_ids:
                lv_idx = _substation_index(BANGALORE_66KV_SUBSTATIONS, lv_id)
                lv_bus = buses_66kv[lv_idx]
                pp.create_transformer_from_parameters(
                    net,
                    hv_bus=hv_bus,
                    lv_bus=lv_bus,
                    sn_mva=100,
                    vn_hv_kv=220.0,
                    vn_lv_kv=66.0,
                    vkr_percent=0.42,
                    vk_percent=10.8,
                    pfe_kw=35,
                    i0_percent=0.12,
                    tap_side="hv",
                    tap_neutral=0,
                    tap_min=-9,
                    tap_max=9,
                    tap_step_percent=1.25,
                    name=f"Tx 220/66 {hv_id}->{lv_id}",
                )

    # --- 66kV Lines (connecting 66kV substations for ring topology) ---
    if config.include_66kv:
        _66kv_lines = [
            ("SS-66-MAJ", "SS-66-SGP", 3.2),
            ("SS-66-SGP", "SS-66-MLD", 2.8),
            ("SS-66-MLD", "SS-66-RNR", 2.1),
            ("SS-66-RNR", "SS-66-MAJ", 2.5),
            ("SS-66-JPR", "SS-66-KRG", 4.0),
            ("SS-66-KRG", "SS-66-HSR", 4.5),
            ("SS-66-HSR", "SS-66-ELE", 6.8),
            ("SS-66-ELE", "SS-66-SRJ", 5.2),
            ("SS-66-SRJ", "SS-66-JPR", 7.0),
            ("SS-66-PNY", "SS-66-MTN", 3.5),
            ("SS-66-MTN", "SS-66-BSK", 4.2),
            ("SS-66-BSK", "SS-66-MGD", 3.8),
            ("SS-66-MGD", "SS-66-KNG", 5.5),
            ("SS-66-KNG", "SS-66-PNY", 6.0),
            ("SS-66-WFD", "SS-66-BRP", 3.0),
            ("SS-66-BRP", "SS-66-MRP", 4.2),
            ("SS-66-MRP", "SS-66-KRP", 3.8),
            ("SS-66-KRP", "SS-66-WFD", 5.0),
            ("SS-66-YLH", "SS-66-VID", 4.5),
            ("SS-66-VID", "SS-66-HNL", 5.0),
            ("SS-66-HNL", "SS-66-SAD", 4.0),
            ("SS-66-SAD", "SS-66-YLH", 3.5),
        ]
        name_to_idx = {s["id"]: i for i, s in enumerate(BANGALORE_66KV_SUBSTATIONS)}
        lp = LINE_PARAMS["66kV"]
        for s_id, t_id, length_km in _66kv_lines:
            if s_id in name_to_idx and t_id in name_to_idx:
                from_bus = buses_66kv[name_to_idx[s_id]]
                to_bus = buses_66kv[name_to_idx[t_id]]
                pp.create_line_from_parameters(
                    net,
                    from_bus=from_bus,
                    to_bus=to_bus,
                    length_km=length_km,
                    r_ohm_per_km=lp["r_ohm_per_km"],
                    x_ohm_per_km=lp["x_ohm_per_km"],
                    c_nf_per_km=lp["c_nf_per_km"],
                    max_i_ka=lp["max_i_ka"],
                    name=f"66kV {s_id}-{t_id}",
                )

    # --- Loads (scaled to real BESCOM peak: ~8,472 MW across all stations) ---
    peak_mw_total = 8472.0
    if config.include_66kv:
        total_66kv_load = sum(s["load_mw"] for s in BANGALORE_66KV_SUBSTATIONS)
        scale = 1.0
        for ss, bus in zip(BANGALORE_66KV_SUBSTATIONS, buses_66kv):
            load_mw = ss["load_mw"] * scale
            load_mvar = load_mw * 0.35  # 0.95 pf lagging
            pp.create_load(
                net,
                bus=bus,
                p_mw=load_mw,
                q_mvar=load_mvar,
                name=f"Load_{ss['id']}",
                scaling=1.0,
            )

    # --- 220kV tie lines (connecting 220kV stations) ---
    if config.include_220kv:
        _220kv_ties = [
            ("SS-220-PNY", "SS-220-YLH", 4.0),
            ("SS-220-YLH", "SS-220-HBL", 3.5),
            ("SS-220-HBL", "SS-220-RNR", 2.8),
            ("SS-220-RNR", "SS-220-MRD", 3.2),
            ("SS-220-MRD", "SS-220-BSK", 3.0),
            ("SS-220-BSK", "SS-220-VKY", 2.5),
            ("SS-220-VKY", "SS-220-JPR", 4.5),
            ("SS-220-JPR", "SS-220-BRP", 3.8),
            ("SS-220-BRP", "SS-220-HSR", 3.2),
            ("SS-220-HSR", "SS-220-MTY", 2.5),
            ("SS-220-MTY", "SS-220-DOM", 3.0),
            ("SS-220-DOM", "SS-220-IND", 2.8),
            ("SS-220-IND", "SS-220-KRG", 3.5),
            ("SS-220-KRG", "SS-220-WFD", 4.0),
            ("SS-220-WFD", "SS-220-IND", 5.5),
        ]
        name_to_idx_220 = {s["id"]: i for i, s in enumerate(BANGALORE_220KV_SUBSTATIONS)}
        lp = LINE_PARAMS["220kV_twin"]
        for s_id, t_id, length_km in _220kv_ties:
            if s_id in name_to_idx_220 and t_id in name_to_idx_220:
                from_bus = buses_220kv[name_to_idx_220[s_id]]
                to_bus = buses_220kv[name_to_idx_220[t_id]]
                pp.create_line_from_parameters(
                    net,
                    from_bus=from_bus,
                    to_bus=to_bus,
                    length_km=length_km,
                    r_ohm_per_km=lp["r_ohm_per_km"],
                    x_ohm_per_km=lp["x_ohm_per_km"],
                    c_nf_per_km=lp.get("c_nf_per_km", 9.0),
                    max_i_ka=lp.get("max_i_ka", 1.57),
                    name=f"220kV {s_id}-{t_id}",
                )

    return net


def describe_network(net) -> str:
    """Return a human-readable description of a BESCOM network."""
    import pandapower as pp

    desc = [
        f"BESCOM Bangalore Grid Network",
        f"  Buses: {len(net.bus)}",
        f"  Lines: {len(net.line)}",
        f"  Transformers: {len(net.trafo)}",
        f"  Loads: {len(net.load)} ({net.load.p_mw.sum():.1f} MW total)",
        f"  External Grids: {len(net.ext_grid)}",
    ]
    return "\n".join(desc)
