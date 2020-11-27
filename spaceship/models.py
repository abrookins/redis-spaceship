from enum import Enum
from dataclasses import dataclass


class Direction(Enum):
    """Directions in space are tracked using cardinal directions."""
    N = 1
    NE = 2
    E = 3
    SE = 4
    S = 5
    SW = 6
    W = 7
    NW = 8


@dataclass
class Velocity:
    speed_kmh: float
    direction: Direction
