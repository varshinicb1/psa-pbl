from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dt_contracts.models import ExplanationPacket, GridGraphSnapshot


@dataclass(frozen=True)
class TwinModelOutput:
    """
    Standard output from the intelligence model.
    """

    prediction: Dict[str, Any]
    explanation: Optional[ExplanationPacket]


class TwinModel(ABC):
    """
    Abstract interface for all digital-twin intelligence models (ML or hybrid).
    """

    @abstractmethod
    def predict(self, snapshot: GridGraphSnapshot) -> TwinModelOutput:
        raise NotImplementedError

