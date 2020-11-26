from dataclasses import dataclass
from enum import Enum
from typing import Protocol, List
from redis import Redis
from . import keys

r = Redis()


# Math Shit
#
# weight = mass * gravity (9.8 on earth)
# resultant force = thrust – weight
# acceleration = resultant force (newtons, N) divided by mass (kilograms, kg).


class Direction(Enum):
    """Directions in space are still tracked using cardinal directions."""
    N = 1
    NE = 2
    E = 3
    SE = 4
    S = 5
    SW = 6
    W = 7
    NW = 8
    NW = 8


@dataclass
class Velocity:
    speed_kmh: float
    direction: Direction = None


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
    def activate(self, units: int, direction: Direction):
        """Burn the specified number of fuel units pointed in the given direction."""

    def cut(self):
        """Stop burning fuel."""


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
                 mass_kg: float,
                 current_gravity: float,
                 forward_thruster: PropulsionSystem,
                 aft_thruster: PropulsionSystem,
                 decks: List[Deck]) -> None:
        self.mass_kg = mass_kg
        self.forward_thruster = forward_thruster
        self.aft_thruster = aft_thruster
        self.decks = {deck.name: deck for deck in decks}
        self.current_velocity = Velocity(0, Direction.N)

    @property
    def weight(self):
        return self.mass_kg * self.current_gravity

    def accelerate(self, target_velocity: Velocity):
        fuel_units = 10  # TODO: how many units to burn for desired speed?
        direction = target_velocity.direction

        if direction in (Direction.N, Direction.NE, Direction.NW):
            self.aft_thruster.fire(fuel_units, direction)
        else:
            self.forward_thruster.fire(fuel_units, direction)


class PipelineIonThruster(PropulsionSystem):
    # TODO: Specific impulse? Need thrust per fuel unit?
    # Can we calculate with Thrust-specific fuel consumption?
    # Get examples of these from the space shuttle launches.
    MAX_FUEL_BURN_PER_CYCLE = 5
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons!

    def __init__(self, redis_client: Redis, ship: Ship):
        self.redis = redis_client

    def fire(self, fuel_units: int, direction: Direction):
        key = keys.ion_thruster_fuel_key()

        if fuel_units <= self.MAX_FUEL_BURN_PER_CYCLE:
            self.redis.decr(key, fuel_units)

        with self.redis.pipeline(transaction=False):
            for _ in fuel_units:
                self.redis.decr(keys.ion_thruster_fuel_key())
