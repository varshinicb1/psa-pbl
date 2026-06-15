"""
Centralized configuration management for the Grid Digital Twin.

Supports environment-based configuration for:
- Data paths
- Simulation parameters
- API/WebSocket settings
- Logging configuration
- Performance tuning

Usage:
    from config import settings
    print(settings.data_dir)
    print(settings.VOLTAGE_BOUNDS)
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class SimulationSettings(BaseSettings):
    """Simulation parameters."""

    # Voltage bounds for anomaly detection (per unit)
    VOLTAGE_LOWER_BOUND: float = Field(default=0.95, description="Lower voltage bound (p.u.)")
    VOLTAGE_UPPER_BOUND: float = Field(default=1.05, description="Upper voltage bound (p.u.)")

    # Tick/step parameters
    TICK_INTERVAL_SECONDS: float = Field(default=1.0, description="Seconds between ticks")
    MAX_POWERFLOW_ITERATIONS: int = Field(default=50, description="Max PF iterations")
    POWERFLOW_TOLERANCE: float = Field(default=1e-6, description="PF convergence tolerance")

    # Anomaly detection
    ANOMALY_PERCENTILE_THRESHOLD: int = Field(default=90, description="Percentile for anomaly")
    MIN_AFFECTED_NODES: int = Field(default=1, description="Min nodes for anomaly event")

    class Config:
        env_prefix = "DT_SIM_"
        case_sensitive = False


class APISettings(BaseSettings):
    """API and WebSocket settings."""

    HOST: str = Field(default="127.0.0.1", description="API host")
    PORT: int = Field(default=8000, description="API port")
    WORKERS: int = Field(default=1, description="Number of worker processes")

    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: float = Field(default=30.0, description="WS heartbeat interval (seconds)")
    WS_MAX_CONNECTIONS: int = Field(default=100, description="Max concurrent connections")
    WS_MESSAGE_TIMEOUT: float = Field(default=5.0, description="WS send timeout (seconds)")

    # CORS
    CORS_ORIGINS: list = Field(default=["http://localhost:5173", "http://localhost:3000"])

    class Config:
        env_prefix = "DT_API_"
        case_sensitive = False


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    LEVEL: str = Field(default="INFO", description="Log level")
    FORMAT: str = Field(
        default="json", description="Log format (json or text)", pattern="^(json|text)$"
    )
    FILE: Optional[Path] = Field(default=None, description="Log file path")
    CONSOLE: bool = Field(default=True, description="Log to console")

    class Config:
        env_prefix = "DT_LOG_"
        case_sensitive = False


class PathSettings(BaseSettings):
    """Path configuration."""

    # Data directory
    DATA_DIR: Optional[Path] = Field(
        default=None, description="Data directory (defaults to ./data)"
    )

    # Log directory
    LOG_DIR: Optional[Path] = Field(default=None, description="Log directory (defaults to ./logs)")

    # Temp directory
    TEMP_DIR: Optional[Path] = Field(default=None, description="Temp directory (defaults to ./tmp)")

    class Config:
        env_prefix = "DT_PATH_"
        case_sensitive = False

    def resolve_data_dir(self) -> Path:
        """Get data directory path, creating if needed."""
        if self.DATA_DIR:
            data_dir = self.DATA_DIR
        else:
            data_dir = Path.cwd() / "data"

        data_dir = data_dir.resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def resolve_log_dir(self) -> Path:
        """Get log directory path, creating if needed."""
        if self.LOG_DIR:
            log_dir = self.LOG_DIR
        else:
            log_dir = Path.cwd() / "logs"

        log_dir = log_dir.resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def resolve_temp_dir(self) -> Path:
        """Get temp directory path, creating if needed."""
        if self.TEMP_DIR:
            temp_dir = self.TEMP_DIR
        else:
            temp_dir = Path.cwd() / "tmp"

        temp_dir = temp_dir.resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir


class Settings(BaseSettings):
    """Root settings combining all configuration sections."""

    # Environment
    ENV: str = Field(default="development", description="Environment (development, staging, production)")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # Sub-configurations
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    class Config:
        env_nested_delimiter = "__"
        env_file = ".env"
        case_sensitive = False
        arbitrary_types_allowed = True


# Global settings instance
_settings: Optional[Settings] = None


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """
    Load and initialize settings.

    Args:
        env_file: Optional path to .env file (defaults to .env in cwd)

    Returns:
        Settings instance
    """
    global _settings

    if env_file:
        os.environ["ENV_FILE"] = str(env_file)

    _settings = Settings()
    return _settings


def get_settings() -> Settings:
    """
    Get global settings instance (loaded).

    Returns:
        Settings instance

    Raises:
        RuntimeError: If settings not yet loaded
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


# Convenience access
settings = get_settings()
