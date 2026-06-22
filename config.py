"""
Centralized configuration for the Metro Grid Digital Twin.

All settings are configurable via environment variables for production
deployments. Supports nested configuration with Pydantic BaseSettings.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class SimulationSettings(BaseSettings):
    VOLTAGE_LOWER_BOUND: float = Field(default=0.95, ge=0.0, le=2.0)
    VOLTAGE_UPPER_BOUND: float = Field(default=1.05, ge=0.0, le=2.0)
    TICK_INTERVAL_SECONDS: float = Field(default=1.0, ge=0.01)
    MAX_POWERFLOW_ITERATIONS: int = Field(default=50, ge=1)
    POWERFLOW_TOLERANCE: float = Field(default=1e-6)
    ANOMALY_PERCENTILE_THRESHOLD: int = Field(default=90, ge=0, le=100)
    LOADING_THRESHOLD_PERCENT: float = Field(default=90.0, ge=0, le=200)
    MAX_TICK_HISTORY: int = Field(default=5000, ge=100)
    S3_BUCKET: Optional[str] = Field(default=None)

    class Config:
        env_prefix = "DT_SIM_"
        case_sensitive = False


class APISettings(BaseSettings):
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000, ge=1024, le=65535)
    WORKERS: int = Field(default=4, ge=1, le=32)
    WS_HEARTBEAT_INTERVAL: float = Field(default=15.0)
    WS_MAX_CONNECTIONS: int = Field(default=500)
    WS_MESSAGE_TIMEOUT: float = Field(default=5.0)
    CORS_ORIGINS: list = Field(default=["*"])
    RATE_LIMIT_PER_MINUTE: int = Field(default=1000)

    class Config:
        env_prefix = "DT_API_"
        case_sensitive = False


class LoggingSettings(BaseSettings):
    LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    FORMAT: str = Field(default="json", pattern="^(json|text)$")
    FILE: Optional[Path] = Field(default=None)
    CONSOLE: bool = Field(default=True)
    CORRELATION_ID_ENABLED: bool = Field(default=True)

    class Config:
        env_prefix = "DT_LOG_"
        case_sensitive = False


class MLSettings(BaseSettings):
    ENSEMBLE_ENABLED: bool = Field(default=True)
    ZSCORE_THRESHOLD: float = Field(default=3.0, ge=1.0)
    ROC_THRESHOLD: float = Field(default=0.05, ge=0.0)
    ANOMALY_CONFIDENCE_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    MODEL_PATH: Optional[Path] = Field(default=None)

    class Config:
        env_prefix = "DT_ML_"
        case_sensitive = False


class SCADASettings(BaseSettings):
    IEC61850_ENABLED: bool = Field(default=False)
    DNP3_ENABLED: bool = Field(default=False)
    MODBUS_ENABLED: bool = Field(default=False)
    SCAN_RATE_MS: int = Field(default=1000)

    class Config:
        env_prefix = "DT_SCADA_"
        case_sensitive = False


class RedisSettings(BaseSettings):
    HOST: str = Field(default="localhost")
    PORT: int = Field(default=6379)
    DB: int = Field(default=0)
    PASSWORD: Optional[str] = Field(default=None)
    SENTINEL_HOSTS: Optional[str] = Field(default=None)

    class Config:
        env_prefix = "REDIS_"
        case_sensitive = False


class SecuritySettings(BaseSettings):
    API_KEY_SECRET: str = Field(default="change-me-in-production")
    JWT_SECRET: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    TOKEN_EXPIRY_HOURS: int = Field(default=24)
    AUDIT_ENABLED: bool = Field(default=True)
    RATE_LIMITING_ENABLED: bool = Field(default=True)

    class Config:
        env_prefix = "DT_SEC_"
        case_sensitive = False


class Settings(BaseSettings):
    ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = Field(default=False)

    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    scada: SCADASettings = Field(default_factory=SCADASettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    class Config:
        env_nested_delimiter = "__"
        env_file = ".env"
        case_sensitive = False
        arbitrary_types_allowed = True


_settings: Optional[Settings] = None


def load_settings(env_file: Optional[Path] = None) -> Settings:
    global _settings
    if env_file:
        os.environ["ENV_FILE"] = str(env_file)
    _settings = Settings()
    return _settings


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


settings = get_settings()
