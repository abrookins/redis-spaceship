from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Union
import marshmallow

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
class Object:
    name: str
    mass: float
    type: str = "object"


@dataclass
class Person:
    name: str
    mass: float
    type: str = "person"


@dataclass
class Vehicle:
    name: str
    base_mass: float
    objects: Dict[str, Union[Person, Object]] = field(default_factory=dict)
    type: str = "vehicle"

    @property
    def mass(self) ->float:
        return self.base_mass + sum(o.mass for o in self.objects.values())


velocity_schema = class_schema(Velocity)()
direction_schema = class_schema(Direction)()
event_schema = class_schema(Event)()
object_schema = class_schema(Object)()
person_schema = class_schema(Person)()
vehicle_schema = class_schema(Vehicle)()


# A dictionary of object schemas, keyed by type. We can use
# this to look up an object schema given its type, e.g.
# "person".
object_schemas_by_type = {
    "person": person_schema,
    "object": object_schema,
    "vehicle": vehicle_schema,
}
