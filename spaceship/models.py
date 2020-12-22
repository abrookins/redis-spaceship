from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

from marshmallow_dataclass import class_schema


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


@dataclass(order=True)
class Event:
    timestamp: int
    data: Dict[str, Any]


@dataclass
class Person:
    name: str
    mass_kg: float
    type: str = "person"


velocity_schema = class_schema(Velocity)()
direction_schema = class_schema(Direction)()
event_schema = class_schema(Event)()
person_schema = class_schema(Person)()


# A dictionary of object schemas, keyed by type. We can use
# this to look up an object schema given its type, e.g.
# "person".
object_schemas_by_type = {
    "person": person_schema
}
