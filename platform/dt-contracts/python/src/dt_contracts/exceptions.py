"""
Custom exception hierarchy for the Grid Digital Twin.

All exceptions are derived from base classes that include error codes
for better error tracking and debugging.
"""


class GridDigitalTwinError(Exception):
    """Base exception for all Grid Digital Twin errors."""

    error_code: str = "UNKNOWN_ERROR"
    http_status: int = 500

    def __init__(self, message: str, error_code: str = None, **context):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (overrides default)
            **context: Additional context fields for logging
        """
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code
        self.context = context


# Configuration & Initialization Errors


class ConfigurationError(GridDigitalTwinError):
    """Configuration is invalid or missing."""

    error_code = "CONFIG_ERROR"
    http_status = 500


class PathResolutionError(GridDigitalTwinError):
    """Unable to resolve required file/directory path."""

    error_code = "PATH_ERROR"
    http_status = 500


class DependencyError(GridDigitalTwinError):
    """Required dependency not available."""

    error_code = "DEPENDENCY_ERROR"
    http_status = 500


# Simulation & Grid Errors


class GridSimulationError(GridDigitalTwinError):
    """Error during grid simulation/powerflow calculation."""

    error_code = "SIM_ERROR"
    http_status = 500


class GridDataError(GridDigitalTwinError):
    """Error in grid data format or validation."""

    error_code = "GRID_DATA_ERROR"
    http_status = 400


class PowerFlowError(GridSimulationError):
    """Power flow calculation failed."""

    error_code = "PF_ERROR"
    http_status = 500


class NetworkNotConverged(PowerFlowError):
    """Power flow did not converge."""

    error_code = "PF_NO_CONVERGE"
    http_status = 422


# Adapter Errors


class AdapterError(GridDigitalTwinError):
    """Base error for simulator adapters."""

    error_code = "ADAPTER_ERROR"
    http_status = 500


class AdapterInitializationError(AdapterError):
    """Failed to initialize adapter."""

    error_code = "ADAPTER_INIT_ERROR"
    http_status = 500


class AdapterExecutionError(AdapterError):
    """Error during adapter execution (subprocess, etc)."""

    error_code = "ADAPTER_EXEC_ERROR"
    http_status = 500


class AdapterTimeoutError(AdapterError):
    """Adapter execution timed out."""

    error_code = "ADAPTER_TIMEOUT"
    http_status = 504


class AdapterNotImplemented(AdapterError):
    """Adapter not yet implemented."""

    error_code = "ADAPTER_NOT_IMPL"
    http_status = 501


# API & I/O Errors


class ValidationError(GridDigitalTwinError):
    """Input validation failed."""

    error_code = "VALIDATION_ERROR"
    http_status = 422


class InvalidRequest(GridDigitalTwinError):
    """Invalid API request."""

    error_code = "INVALID_REQUEST"
    http_status = 400


class NotFoundError(GridDigitalTwinError):
    """Requested resource not found."""

    error_code = "NOT_FOUND"
    http_status = 404


class ConflictError(GridDigitalTwinError):
    """Resource conflict (already exists, state conflict, etc)."""

    error_code = "CONFLICT"
    http_status = 409


# State Management Errors


class StateError(GridDigitalTwinError):
    """Invalid state transition or operation."""

    error_code = "STATE_ERROR"
    http_status = 422


class StoreError(GridDigitalTwinError):
    """Error in data store/persistence."""

    error_code = "STORE_ERROR"
    http_status = 500


# Concurrent Operation Errors


class ConcurrencyError(GridDigitalTwinError):
    """Concurrency-related error."""

    error_code = "CONCURRENCY_ERROR"
    http_status = 409


class LockTimeoutError(ConcurrencyError):
    """Failed to acquire lock within timeout."""

    error_code = "LOCK_TIMEOUT"
    http_status = 408


# Orchestration Errors


class OrchestrationError(GridDigitalTwinError):
    """Error in orchestration/pipeline."""

    error_code = "ORCHESTRATION_ERROR"
    http_status = 500


class TickExecutionError(OrchestrationError):
    """Error during tick execution."""

    error_code = "TICK_ERROR"
    http_status = 500


class DataIngestionError(OrchestrationError):
    """Error during data ingestion phase."""

    error_code = "INGEST_ERROR"
    http_status = 400


class StateUpdateError(OrchestrationError):
    """Error during state update phase."""

    error_code = "STATE_UPDATE_ERROR"
    http_status = 500


class PublishError(OrchestrationError):
    """Error during publish phase."""

    error_code = "PUBLISH_ERROR"
    http_status = 500


def error_to_dict(exc: GridDigitalTwinError) -> dict:
    """
    Convert exception to dictionary for API responses.

    Args:
        exc: Exception instance

    Returns:
        Dictionary suitable for JSON response
    """
    return {
        "error": exc.error_code,
        "message": str(exc),
        "context": exc.context if hasattr(exc, "context") else {},
    }
