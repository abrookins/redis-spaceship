from enum import Enum
from typing import Protocol, List
from redis import Redis
from . import keys

r = Redis()


class Direction(Enum):
    N = 1
    NE = 2
    E = 3
    SE = 4
    S = 5
    SW = 6
    W = 7
    NW = 8
    NW = 8


class Propulsion(Protocol):
    def fire(self, units: int, direction: Direction):
        """Burn the specified number of fuel units pointed in the given direction."""


class WeightedObject(Protocol):
    def weight_g(self) -> int:
        """The object's weight in grams."""

    def weight_kg(self) -> int:
        """The object's weight in kilograms."""


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
                 forward_thruster: Propulsion,
                 aft_thruster: Propulsion,
                 decks: List[Deck]) -> None:
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}

    def accelerate(self, direction: Direction, desired_speed_mh: float):
        fuel_units = 10  # TODO: how many units to burn for desired speed?

        if direction in (Direction.N, Direction.NE, Direction.NW):
            self.aft_thruster.fire(fuel_units, direction)
        else:
            self.forward_thruster.fire(fuel_units, direction)


class PipelineIonThruster(Propulsion):
    MAX_FUEL_BURN_PER_CYCLE = 5

    def __init__(self, redis_client: Redis, ship: Ship):
        self.redis = redis_client

    def fire(self, fuel_units: int, direction: Direction):
        key = keys.ion_thruster_fuel_key()

        if fuel_units <= self.MAX_FUEL_BURN_PER_CYCLE:
            self.redis.decr(key, fuel_units)

        with self.redis.pipeline(transaction=False):
            for _ in fuel_units:
                self.redis.decr(keys.ion_thruster_fuel_key())
