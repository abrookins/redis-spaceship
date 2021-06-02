import time
from typing import Dict, List, Protocol

from .models import Event, Velocity


class EventLog(Protocol):
    def events(self, start: int, end: int) -> List[Event]:
        """Return events in the log."""

    def add(self, event: Event) -> None:
        """Add an event."""


class PropulsionSystem(Protocol):
    """A propulsion system."""
    def fire(self, target_velocity: Velocity):
        """Burn fuel until reaching the target velocity."""


class ShipObject(Protocol):
    """An object inside the ship, which has mass."""
    @property
    def mass(self) -> float:
        """The object's mass in kilograms."""

    @property
    def name(self) -> str:
        """The object's name."""


class ShipObjectContainer(ShipObject):
    """A ship object that can contain other ShipObjects."""
    objects: Dict[str, ShipObject]


class Deck(Protocol):
    """The deck of a ship."""
    name: str  # The name of this deck.
    max_storage_kg: float  # The maximum storage of this deck in kilograms.

    def items(self) -> List[ShipObject]:
        """Get the items stored in this deck."""

    def store(self, object: ShipObject):
        """Store an object in this deck."""

    def get(self, name: str) -> ShipObject:
        """Return an item stored in the deck by name."""

    def remove(self, name: str) -> ShipObject:
        """Remove and return an item stored in the deck by name."""

    @property
    def capacity_kg(self) -> float:
        """The current capacity of this deck."""

    @property
    def stored_mass(self) -> float:
       """The current stored mass (in kilograms) of this deck."""



class Ship(Protocol):
    """A ship."""
    thruster: PropulsionSystem
    decks: List[Deck]
    event_log: EventLog
    low_fuel_threshold: float

    @property
    def fuel(self) -> float:
        """Current fuel."""

    @property
    def mass(self) -> float:
        """The total current mass of the ship, including decks."""
        return self.base_mass + sum(deck.stored_mass for deck in self.decks.values())

    @property
    def weight_kg(self) -> float:
        """The weight of the ship given its mass and current gravity."""
        return self.mass * self.current_gravity

    def accelerate(self, target_velocity: Velocity):
        """Accelerate the ship to a target velocity.

        Acceleration stops when either the ship reaches that velocity, or
        remaining fuel reaches the configured low fuel threshold.
        """
        for fuel_burned, next_burn in self.thruster.fire(target_velocity, self.weight_kg, self.mass):
            self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned, 'next_burn': next_burn}))
            remaining_fuel = self.fuel - self.low_fuel_threshold
            if remaining_fuel < next_burn:
                break

    def store(self, deck_name: str, obj: ShipObject):
        """Store an object in a deck."""
        self.decks[deck_name].store(obj)
