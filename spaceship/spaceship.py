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
    def __init__(self, event_log: EventLog, base_mass_kg: float,
                 thruster: PropulsionSystem, decks: List[Deck]) -> None:
        self.base_mass_kg = base_mass_kg
        self.thruster = thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log

    @property
    def mass_kg(self):
        return self.base_mass_kg + sum(deck.stored_mass_kg for deck in self.decks.values())

    @property
    def weight_kg(self):
        return self.mass_kg * self.current_gravity

    def accelerate(self, target_velocity: Velocity):
        for fuel_burned in self.thruster.fire(target_velocity, self.weight_kg, self.mass_kg):
            self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))

    def store(self, deck_name: str, obj: WeightedObject):
        self.decks[deck_name].store(obj)


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
    def base_mass_kg(self):
        return self.data['base_mass_kg']

    @base_mass_kg.setter
    def base_mass_kg(self, base_mass_kg):
        self.data['base_mass_kg'] = base_mass_kg


class RedisShip(ShipBase):
    def __init__(self, redis: Redis, *args, **kwargs):
        self.data = redis
        super().__init__(*args, **kwargs)
        self.data['current_velocity'] = velocity_schema.dumps(Velocity(0, Direction.N))

    @property
    def current_gravity(self):
        return float(self.data[keys.ship_current_gravity()])

    @property
    def base_weight_kg(self):
        return float(self.data[keys.ship_current_mass_kg()])


class DictDeck(Deck):
    def __init__(self, name: str, data: Dict[Any, Any], max_storage_kg: float) -> None:
        self.name = name
        self.max_storage_kg = max_storage_kg

        if 'decks' not in data:
            data['decks'] = {}

        self.data = data['decks'][name] = {'objects': {}}
        self.storage = self.data['objects']

    @property
    def stored_mass_kg(self):
        return sum([obj.weight_kg for obj in self.data['objects'].values()])

    def capacity(self) -> float:
        """The current capacity of this deck."""
        return self.max_storage_kg - self.stored_mass_kg

    def store(self, object: Union[WeightedObject, NamedObject]):
        """Store an object in this deck."""
        if not self.capacity:
            raise NoCapacityError
        self.storage[object.name] = object


class DictThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, data: Dict[Any, Any]):
        self.data = data

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass_kg: float):
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass_kg
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


class RedisThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, data: Redis):
        self.data = data

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass_kg: float):
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass_kg
        acceleration_per_second_kmh = acceleration_per_second_ms * 3.6
        remainder, seconds_to_burn = math.modf(target_velocity.speed_kmh /
                                               acceleration_per_second_kmh)
        key = keys.ship_current_speed(target_velocity.direction.value)

        with self.data.pipeline(transaction=False) as p:
            # TODO: Coroutine -- yield from caller; caller decides
            # whether to continue the burn after examining fuel burned.
            for _ in range(int(seconds_to_burn)):
                self.data.incrbyfloat(key, acceleration_per_second_kmh)
                yield self.FUEL_BURNED_PER_SECOND
            p.execute()

        if remainder:
            self.data.incrbyfloat(key, acceleration_per_second_kmh * remainder)
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
