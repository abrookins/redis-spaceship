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

