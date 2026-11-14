"""Input models preserve raw values for later validation."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class InputRecord:
    index: int
    data: Any
    input_problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadedDataset:
    records: tuple[InputRecord, ...]
    input_format: str
    filename: str


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFORMATIONAL = "informational"


@dataclass(frozen=True)
class Issue:
    record_id: str
    record_index: int
    issue_type: str
    description: str
    severity: Severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_index": self.record_index,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity.value,
        }
