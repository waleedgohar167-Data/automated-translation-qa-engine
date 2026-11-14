"""Input models preserve raw values for later validation."""

from dataclasses import dataclass
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
