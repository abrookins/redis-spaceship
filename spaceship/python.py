import bisect
import math
from collections import defaultdict
from typing import Any, Dict, List, Union

from .models import Direction, Event, Velocity
from .protocols import (Deck, EventLog, PropulsionSystem, ShipObject, Ship)
from .errors import NoCapacityError


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

    @property
    def stored_mass(self):
        return sum([obj.mass for obj in self.data['objects'].values()])

    @property
    def capacity_mass(self) -> float:
        """The current capacity of this deck."""
        return self.max_storage_kg - self.stored_mass

    def store(self, object: ShipObject):
        """Store an object in this deck."""
        if object.mass > self.capacity_mass:
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
        target_burn = int(seconds_to_burn)

        for i in range(target_burn):
            next_burn = self.FUEL_BURNED_PER_SECOND if i < target_burn else remainder
            self.data['speed_kmh'][direction] += acceleration_per_second_kmh
            yield self.FUEL_BURNED_PER_SECOND, next_burn

        if remainder:
            self.data['speed_kmh'][direction] += acceleration_per_second_kmh * remainder
            yield self.FUEL_BURNED_PER_SECOND * remainder, 0


class DictShip(Ship):
    def __init__(self, data: Dict[Any, Any], event_log: EventLog, base_mass: float, thruster: PropulsionSystem,
                 decks: List[Deck], low_fuel_threshold: float = 0) -> None:
        self.data = data
        self.base_mass = base_mass
        self.thruster = thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log
        self.data['current_velocity'] = Velocity(0, Direction.N)
        self.data['acceleration'] = defaultdict(float)
        self.low_fuel_threshold = low_fuel_threshold  # TODO: Belongs in data?

    @property
    def fuel(self):
        total = self.data['current_fuel']  # TODO: This doesn't make sense. :P
        burned = sum([l.data['fuel_burned'] for l in self.event_log.events
                    if 'fuel_burned' in l.data])
        return total - burned

    @property
    def current_gravity(self):
        return self.data['current_gravity']

    @property
    def base_mass(self):
        return self.data['base_mass']

    @base_mass.setter
    def base_mass(self, base_mass):
        self.data['base_mass'] = base_mass


