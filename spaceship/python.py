import bisect
import math
from collections import defaultdict
from typing import Any, Dict, List, Union

from .models import Direction, Event, Velocity
from .protocols import (Deck, EventLog, PropulsionSystem, ShipObject)
from .spaceship import NoCapacityError, ShipBase


class ListEventLog(EventLog):
    def __init__(self):
        self.events = []

    def __len__(self):
        return len(self.events)

    def events(self, start: int, end: int) -> List[Event]:
        start_idx = bisect.bisect_left(self.events, Event(timestamp=start, description="")) + 1
        end_idx = bisect.bisect_right(self.events, Event(timestamp=end, description=""))
        return self.events[start_idx + 1:end_idx]

    def add(self, event: Event):
        bisect.insort(self.events, event)


class DictDeck(Deck):
    def __init__(self, name: str, data: Dict[Any, Any], max_storage_kg: float) -> None:
        self.name = name
        self.max_storage_kg = max_storage_kg

        if 'decks' not in data:
            data['decks'] = {}

        self.data = data['decks'][name] = {'objects': {}}
        self.storage = self.data['objects']

    def stored_mass(self):
        return sum([obj.mass for obj in self.data['objects'].values()])

    @property
    def capacity_mass(self) -> float:
        """The current capacity of this deck."""
        return self.max_storage_kg - self.stored_mass()

    def store(self, object: ShipObject):
        """Store an object in this deck."""
        if not self.capacity_mass:
            raise NoCapacityError
        self.storage[object.name] = object


class DictThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, data: Dict[Any, Any]):
        self.data = data

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass: float):
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass
        acceleration_per_second_kmh = acceleration_per_second_ms * 3.6
        remainder, seconds_to_burn = math.modf(target_velocity.speed_kmh /
                                               acceleration_per_second_kmh)

        direction = target_velocity.direction.value

        for _ in range(int(seconds_to_burn)):
            self.data['speed_kmh'][direction] += acceleration_per_second_kmh
            yield self.FUEL_BURNED_PER_SECOND

        if remainder:
            self.data['speed_kmh'][direction] += acceleration_per_second_kmh * remainder
            yield self.FUEL_BURNED_PER_SECOND * remainder


class DictShip(ShipBase):
    def __init__(self, data: Dict[Any, Any], *args, **kwargs):
        self.data = data
        super().__init__(*args, **kwargs)
        self.data['current_velocity'] = Velocity(0, Direction.N)
        self.data['acceleration'] = defaultdict(float)

    @property
    def current_gravity(self):
        return self.data['current_gravity']

    @property
    def base_mass(self):
        return self.data['base_mass']

    @base_mass.setter
    def base_mass(self, base_mass):
        self.data['base_mass'] = base_mass


