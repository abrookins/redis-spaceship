from typing import Protocol, List

from .models import Velocity, Event


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
    @property
    def mass_kg(self) -> float:
        """The object's mass in kilograms."""

    @property
    def name(self) -> str:
        """The object's name."""


class Deck(Protocol):
    """The deck of a ship."""
    name: str  # The name of this deck.
    max_storage_kg: float  # The maximum storage of this deck in kilograms.

    def capacity(self) -> float:
        """The current capacity of this deck."""

    def items(self) -> List[ShipObject]:
        """Get the items stored in this deck."""

    def store(self, object: ShipObject):
        """Store an object in this deck."""

    def get(self, name: str) -> ShipObject:
        """Return an item stored in the deck by name."""

    def remove(self, name: str) -> ShipObject:
        """Remove and return an item stored in the deck by name."""
