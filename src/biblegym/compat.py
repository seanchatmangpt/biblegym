from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

try:
    from gymact.models import Capability, Consequence
except ImportError:
    class Consequence(StrEnum):
        READ = "READ"
        DO = "DO"

    @dataclass(frozen=True)
    class Capability:
        iri: str
        title: str
        consequence: Consequence
        binding: str
