import bisect
import time
from collections import defaultdict
from typing import Protocol, List, Union
from dataclasses import dataclass

from redis import Redis
from .keys import pipeline_thruster_thrust_key
from .models import Direction, Velocity

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
    description: str


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
    def fire(self, units: int, direction: Direction):
        """Burn the specified number of fuel units pointed in the given direction."""


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


class Ship:
    def __init__(self,
                 mass_kg: float,
                 current_gravity: float,
                 forward_thruster: PropulsionSystem,
                 aft_thruster: PropulsionSystem,
                 decks: List[Deck],
                 event_log: EventLog) -> None:
        self.mass_kg = mass_kg
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}
        self.current_velocity = Velocity(0, Direction.N)
        self.current_gravity = current_gravity
        self.event_log = event_log

    @property
    def weight(self):
        return self.mass_kg * self.current_gravity

    def accelerate(self, target_velocity: Velocity):
        fuel_units = 10  # TODO: how many units to burn for desired speed?
        direction = target_velocity.direction

        if direction in (Direction.N, Direction.NE, Direction.NW):
            for fuel_burned in self.aft_thruster.fire(fuel_units, direction):
                self.event_log.add(Event(time.time(), f'fuel burned: {fuel_burned}'))
            return

        for fuel_burned in self.forward_thruster.fire(fuel_units, direction):
            self.event_log.add(Event(time.time(), f'fuel burned: {fuel_burned}'))


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
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons!
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self):
        self.thrust = defaultdict(int)

    def fire(self, fuel_units: int, direction: Direction):
        seconds_to_burn = fuel_units / self.FUEL_BURNED_PER_SECOND
        for _ in range(int(seconds_to_burn)):  # round down
            self.thrust[direction] += self.THRUST_PER_SECOND_NEWTONS
            yield self.FUEL_BURNED_PER_SECOND


class ListEventLog(EventLog):
    def __init__(self):
        self.events = []

    def events(self, start: int, end: int) -> List[Event]:
        start_idx = bisect.bisect_left(self.events, Event(timestamp=start, description="")) + 1
        end_idx = bisect.bisect_right(self.events, Event(timestamp=end, description=""))
        return self.events[start_idx + 1:end_idx]

    def add(self, event: Event):
        bisect.insort(self.events, event)


class PipelineThruster(PropulsionSystem):
    # TODO: Specific impulse? Need thrust per fuel unit?
    # Can we calculate with Thrust-specific fuel consumption?
    # Get examples of these from the space shuttle launches.
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons!
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, redis_client: Redis, ship: Ship):
        self.redis = redis_client

    def fire(self, fuel_units: int, direction: Direction):
        key = pipeline_thruster_thrust_key(direction)
        with self.redis.pipeline(transaction=False):
            for _ in fuel_units:
                self.redis.decr(key)
