import bisect
import math
import time
from collections import defaultdict
from typing import Any, Dict, Protocol, List, Union
from dataclasses import dataclass

from redis import Redis
from . import keys
from .models import Direction, Velocity, direction_schema, velocity_schema

r = Redis()


class NoCapacityError(Exception):
    """There is no more capacity in this object."""


# Math Shit
#
# weight = mass * gravity (9.8 on earth)
# resultant force = thrust – weight
# acceleration = resultant force (newtons, N) divided by mass (kilograms, kg).


@dataclass(order=True)
class Event:
    timestamp: int
    data: Dict[str, Any]


class EventLog(Protocol):
    def events(self, start: int, end: int) -> List[Event]:
        """Return events in the log."""

    def add(self, event: Event) -> None:
        """Add an event."""


class PropulsionSystem(Protocol):
    """A propulsion system.

    TODO: Update language here.

    A propulsion system may be on, at which time it begins burning fuel at
    its currently configured burn rate. This is the amount of fuel it burns
    per second.

    The maximum burn rate is constant.

    The minimum burn rate is zero.

    Propulsion systems have a direction they are currently pointing. Some
    might be fixed, while others can change direction.

    You fire a thurster to turn it on, and it burns at the currently set burn
    rate, producing force.
    """
    def fire(self, direction: Direction):
        """Burn fuel in the given direction."""


class WeightedObject(Protocol):
    @property
    def weight_kg(self) -> float:
        """The object's weight in kilograms."""


class NamedObject(Protocol):
    @property
    def name(self) -> str:
        """The object's name."""


class Deck(Protocol):
    """The deck of a ship."""
    name: str  # The name of this deck.
    max_storage_kg: float  # The maximum storage of this deck in kilograms.

    def capacity(self) -> float:
        """The current capacity of this deck."""

    def store(self, object: WeightedObject):
        """Store an object in this deck."""


class DictShip:
    def __init__(self,
                 data: Dict[Any, Any],
                 event_log: EventLog,
                 base_mass_kg: float,
                 forward_thruster: PropulsionSystem,
                 aft_thruster: PropulsionSystem,
                 decks: List[Deck]) -> None:
        self.base_mass_kg = base_mass_kg
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log

        # TODO: abstract this; supports dicts and redis?
        # boot_brain() method...?
        data['current_velocity'] = Velocity(0, Direction.N)
        data['acceleration'] = defaultdict(float)
        self.data = data

    @property
    def weight(self):
        return self.data['current_mass_kg'] * self.data['current_gravity']

    def accelerate(self, target_velocity: Velocity):
        if target_velocity.direction in (Direction.N, Direction.NE, Direction.NW):
            for fuel_burned in self.aft_thruster.fire(target_velocity):
                self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))
            return

        for fuel_burned in self.forward_thruster.fire(target_velocity):
            self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))

class RedisShip:
    def __init__(self,
                 data: Dict[Any, Any],
                 event_log: EventLog,
                 base_mass_kg: float,
                 forward_thruster: PropulsionSystem,
                 aft_thruster: PropulsionSystem,
                 decks: List[Deck]) -> None:
        self.base_mass_kg = base_mass_kg
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log

        # TODO: abstract this; supports dicts and redis?
        data['current_velocity'] = velocity_schema.dumps(Velocity(0, Direction.N))
        self.data = data

    @property
    def weight(self):
        # TODO: Pipeline
        return self.data['current_mass_kg'] * self.data['current_gravity']

    def accelerate(self, target_velocity: Velocity):
        if target_velocity.direction in (Direction.N, Direction.NE, Direction.NW):
            for fuel_burned in self.aft_thruster.fire(target_velocity):
                self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))
            return

        for fuel_burned in self.forward_thruster.fire(target_velocity):
            self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))


class DictDeck(Deck):
    def __init__(self, name: str, max_storage_kg: float) -> None:
        self.name = name
        self.max_storage_kg = max_storage_kg
        self.storage = {}
        self.stored_weight_kg = 0

    def capacity(self) -> float:
        """The current capacity of this deck."""
        return self.max_storage_kg - self.stored_weight

    def store(self, object: Union[WeightedObject, NamedObject]):
        """Store an object in this deck."""
        if not self.capacity:
            raise NoCapacityError

        self.storage[object.name] = object
        self.stored_weight_kg += object.weight_kg


class DictThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, name: str, data: Dict[Any, Any]):
        self.name = name
        self.data = data
        ship_mass_kg = data['current_mass_kg']
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_mass_kg
        self.acceleration_per_second_kmh = (resultant_force / ship_mass_kg) * 3.6

    def fire(self, target_velocity: Velocity):
        remainder, seconds_to_burn = math.modf(
            target_velocity.speed_kmh / self.acceleration_per_second_kmh)

        direction = target_velocity.direction.value

        for _ in range(int(seconds_to_burn)):
            self.data['speed_kmh'][direction] += self.acceleration_per_second_kmh
            yield self.FUEL_BURNED_PER_SECOND

        if remainder:
            self.data['speed_kmh'][direction] += self.acceleration_per_second_kmh * remainder
            yield self.FUEL_BURNED_PER_SECOND * remainder


class RedisThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, name: str, data: Redis):
        self.name = name
        self.data = data
        ship_mass_kg = float(data.get(keys.ship_current_mass_kg()))
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_mass_kg
        self.acceleration_per_second_kmh = (resultant_force / ship_mass_kg) * 3.6

    def fire(self, target_velocity: Velocity):
        remainder, seconds_to_burn = math.modf(
            target_velocity.speed_kmh / self.acceleration_per_second_kmh)

        key = keys.ship_current_speed(target_velocity.direction)

        with self.data.pipeline(transaction=False) as p:
            # TODO: Coroutine -- yield from caller; caller decides
            # whether to continue the burn after examining fuel burned.
            for _ in range(int(seconds_to_burn)):
                self.data.incrbyfloat(key, self.acceleration_per_second_kmh)
                yield self.FUEL_BURNED_PER_SECOND
            p.execute()

        if remainder:
            self.data.incrbyfloat(key, self.acceleration_per_second_kmh * remainder)
            yield self.FUEL_BURNED_PER_SECOND * remainder


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


