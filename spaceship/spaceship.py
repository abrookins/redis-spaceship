import bisect
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Union

from redis import Redis
from . import keys
from .models import Direction, Velocity, Event, velocity_schema
from .protocols import EventLog, PropulsionSystem, WeightedObject, NamedObject, Deck


class NoCapacityError(Exception):
    """There is no more capacity in this object."""


class ShipBase:
    def __init__(self, data: Dict[Any, Any], event_log: EventLog,
                 base_mass_kg: float, forward_thruster: PropulsionSystem,
                 aft_thruster: PropulsionSystem, decks: List[Deck]) -> None:
        self.base_mass_kg = base_mass_kg
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log
        self.data = data

    @property
    def weight(self):
        # TODO: Allow RedisShip to use Pipeline: get_multi() method on
        # a custom Data class?
        return self.data['current_mass_kg'] * self.data['current_gravity']

    def accelerate(self, target_velocity: Velocity):
        if target_velocity.direction in (Direction.N, Direction.NE,
                                         Direction.NW):
            for fuel_burned in self.aft_thruster.fire(target_velocity):
                self.event_log.add(
                    Event(time.time(), {'fuel_burned': fuel_burned}))
            return

        for fuel_burned in self.forward_thruster.fire(target_velocity):
            self.event_log.add(Event(time.time(),
                                     {'fuel_burned': fuel_burned}))



class DictShip(ShipBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data['current_velocity'] = Velocity(0, Direction.N)
        self.data['acceleration'] = defaultdict(float)


class RedisShip(ShipBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data['current_velocity'] = velocity_schema.dumps(
            Velocity(0, Direction.N))


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
        self.acceleration_per_second_kmh = (resultant_force /
                                            ship_mass_kg) * 3.6

    def fire(self, target_velocity: Velocity):
        remainder, seconds_to_burn = math.modf(
            target_velocity.speed_kmh / self.acceleration_per_second_kmh)

        direction = target_velocity.direction.value

        for _ in range(int(seconds_to_burn)):
            self.data['speed_kmh'][
                direction] += self.acceleration_per_second_kmh
            yield self.FUEL_BURNED_PER_SECOND

        if remainder:
            self.data['speed_kmh'][
                direction] += self.acceleration_per_second_kmh * remainder
            yield self.FUEL_BURNED_PER_SECOND * remainder


class RedisThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, name: str, data: Redis):
        self.name = name
        self.data = data
        ship_mass_kg = float(data.get(keys.ship_current_mass_kg()))
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_mass_kg
        self.acceleration_per_second_kmh = (resultant_force /
                                            ship_mass_kg) * 3.6

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
            self.data.incrbyfloat(key,
                                  self.acceleration_per_second_kmh * remainder)
            yield self.FUEL_BURNED_PER_SECOND * remainder


class ListEventLog(EventLog):
    def __init__(self):
        self.events = []

    def __len__(self):
        return len(self.events)

    def events(self, start: int, end: int) -> List[Event]:
        start_idx = bisect.bisect_left(
            self.events, Event(timestamp=start, description="")) + 1
        end_idx = bisect.bisect_right(self.events,
                                      Event(timestamp=end, description=""))
        return self.events[start_idx + 1:end_idx]

    def add(self, event: Event):
        bisect.insort(self.events, event)
