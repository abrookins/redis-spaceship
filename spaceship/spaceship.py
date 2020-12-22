import time
from typing import List

from .models import Velocity, Event
from .protocols import EventLog, PropulsionSystem, ShipObject, Deck


class NoCapacityError(Exception):
    """There is no more capacity in this object."""


class ShipBase:
    def __init__(self, event_log: EventLog, base_mass_kg: float, thruster: PropulsionSystem,
                 decks: List[Deck]) -> None:
        self.base_mass_kg = base_mass_kg
        self.thruster = thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log

    @property
    def mass_kg(self):
        return self.base_mass_kg + sum(deck.stored_mass_kg() for deck in self.decks.values())

    @property
    def weight_kg(self):
        return self.mass_kg * self.current_gravity

    def accelerate(self, target_velocity: Velocity):
        for fuel_burned in self.thruster.fire(target_velocity, self.weight_kg, self.mass_kg):
            self.event_log.add(Event(time.time(), {'fuel_burned': fuel_burned}))

    def store(self, deck_name: str, obj: ShipObject):
        self.decks[deck_name].store(obj)
