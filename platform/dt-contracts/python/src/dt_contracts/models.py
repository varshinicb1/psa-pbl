"""
Production-grade canonical data models for the Grid Digital Twin.

These models define the contract between all platform components:
simulators, ML engine, SCADA ingestion, dashboard, and external systems.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "2.0.0"


class ExternalRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str
    object_type: str
    object_name: str
    terminal: Optional[str] = None
    phase: Optional[str] = None


class GeographicalCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: Optional[float] = None


class GridNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str = Field(
        description="Bus, BusTerminal, Transformer, Generator, Load, DER, Breaker, Relay, PMU, Substation"
    )
    static: Dict[str, Any] = Field(default_factory=dict)
    dynamic: Dict[str, Any] = Field(default_factory=dict)
    external_refs: List[ExternalRef] = Field(default_factory=list)
    coordinates: Optional[GeographicalCoordinate] = None
    substation_id: Optional[str] = None
    zone: Optional[str] = None


class GridEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str = Field(
        description="Line, Transformer, Switch, ProtectionDevice, MeasurementOf, Containment"
    )
    source: str
    target: str
    static: Dict[str, Any] = Field(default_factory=dict)
    dynamic: Dict[str, Any] = Field(default_factory=dict)
    external_refs: List[ExternalRef] = Field(default_factory=list)


class GridGraphSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default=SCHEMA_VERSION)
    t: str
    topology_hash: str
    topology_version: int = 0
    tick_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[GridNode] = Field(default_factory=list)
    edges: List[GridEdge] = Field(default_factory=list)


class MeasurementQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: Optional[bool] = None
    missing: Optional[bool] = None
    estimated: Optional[bool] = None
    bad_data: Optional[bool] = None
    delay_ms: Optional[float] = Field(default=None, ge=0)
    reason: Optional[str] = None


MeasurementValue = Union[float, int, str, bool]


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    signal: str
    value: MeasurementValue
    unit: Optional[str] = None
    phase: Optional[str] = None
    quality: Optional[MeasurementQuality] = None
    timestamp: Optional[str] = None


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    severity: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None


class TelemetryTick(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default=SCHEMA_VERSION)
    t_event: str
    t_ingest: str
    source: Optional[str] = None
    measurements: List[Measurement] = Field(default_factory=list)
    events: List[TelemetryEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    device_id: str
    desired_state: Optional[Union[str, bool, float, int]] = None
    effective_time: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    approved_by: Optional[str] = None


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default=SCHEMA_VERSION)
    t: str
    plan_id: Optional[str] = None
    actions: List[Action] = Field(default_factory=list)
    expected_outcome: Dict[str, Any] = Field(default_factory=dict)
    risk_score: Optional[float] = Field(default=None, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EntityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    score: float = Field(ge=-100, le=100)


class FeatureScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    feature: str
    score: float = Field(ge=-100, le=100)


class Explanation(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    node_scores: List[EntityScore] = Field(default_factory=list)
    edge_scores: List[EntityScore] = Field(default_factory=list)
    feature_scores: List[FeatureScore] = Field(default_factory=list)
    rationale: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ExplanationPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default=SCHEMA_VERSION)
    t: str
    model_version: str
    target: Dict[str, Any]
    uncertainty: Dict[str, Any] = Field(default_factory=dict)
    physics_residuals: Dict[str, Any] = Field(default_factory=dict)
    explanations: List[Explanation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ml_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ScenarioForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default=SCHEMA_VERSION)
    t: str
    horizon_minutes: int
    predictions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_intervals: Dict[str, List[float]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Alarm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str = Field(
        description="VoltageViolation, Overload, TopologyChange, FrequencyDeviation, ProtectionEvent"
    )
    severity: str = Field(pattern="^(info|warning|critical|emergency)$")
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    message: str
    timestamp: str
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    cleared: bool = False
    cleared_at: Optional[str] = None
