from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FactorHit:
    id: str
    category: str
    label: str
    points: float
    alert: str | None = None