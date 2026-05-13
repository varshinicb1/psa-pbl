from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"


class ExternalRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str
    object_type: str
    object_name: str
    terminal: Optional[str] = None
    phase: Optional[str] = None


class GridNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = Field(description="E.g. BusTerminal, Bus, Transformer, DER, Breaker, Relay, PMU, Substation.")
    static: Dict[str, Any] = Field(default_factory=dict)
    dynamic: Dict[str, Any] = Field(default_factory=dict)
    external_refs: List[ExternalRef] = Field(default_factory=list)


class GridEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str = Field(description="E.g. Line, Transformer, Switch, ProtectionDevice, MeasurementOf, Containment.")
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


MeasurementValue = Union[float, int, str, bool]


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    signal: str
    value: MeasurementValue
    unit: Optional[str] = None
    phase: Optional[str] = None
    quality: Optional[MeasurementQuality] = None


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str


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


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION)
    t: str
    plan_id: Optional[str] = None
    actions: List[Action] = Field(default_factory=list)
    expected_outcome: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EntityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    score: float


class FeatureScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    feature: str
    score: float


class Explanation(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    node_scores: List[EntityScore] = Field(default_factory=list)
    edge_scores: List[EntityScore] = Field(default_factory=list)
    feature_scores: List[FeatureScore] = Field(default_factory=list)


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

