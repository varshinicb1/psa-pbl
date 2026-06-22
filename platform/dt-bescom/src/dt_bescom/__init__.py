"""
BESCOM - Bangalore Electricity Supply Company digital twin integration.

Real-world network models, load profiles, and data acquisition for
the Bangalore metropolitan power grid (BESCOM jurisdiction).
"""

from .network_model import (
    build_bescom_network,
    BESCOMNetworkConfig,
    get_bangalore_substations,
    BANGALORE_400KV_SUBSTATIONS,
    BANGALORE_220KV_SUBSTATIONS,
    BANGALORE_66KV_SUBSTATIONS,
)
from .load_profiles import (
    BESCOMLoadProfile,
    get_bangalore_daily_load_curve,
    generate_bescom_loads,
    INDUSTRIAL_LOAD_PATTERN,
    RESIDENTIAL_LOAD_PATTERN,
    COMMERCIAL_LOAD_PATTERN,
)
from .data_fetcher import (
    fetch_bescom_substations,
    fetch_bescom_ht_lines,
    fetch_bescom_consumption,
    download_all_bescom_data,
    list_available_datasets,
)

__all__ = [
    "build_bescom_network",
    "BESCOMNetworkConfig",
    "get_bangalore_substations",
    "BANGALORE_400KV_SUBSTATIONS",
    "BANGALORE_220KV_SUBSTATIONS",
    "BANGALORE_66KV_SUBSTATIONS",
    "BESCOMLoadProfile",
    "get_bangalore_daily_load_curve",
    "generate_bescom_loads",
    "INDUSTRIAL_LOAD_PATTERN",
    "RESIDENTIAL_LOAD_PATTERN",
    "COMMERCIAL_LOAD_PATTERN",
    "fetch_bescom_substations",
    "fetch_bescom_ht_lines",
    "fetch_bescom_consumption",
    "download_all_bescom_data",
    "list_available_datasets",
]
