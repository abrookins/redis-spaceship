import os
from .models import Direction

DEFAULT_PREFIX = "spaceship:test"

PREFIX = os.environ.get('KEY_PREFIX', DEFAULT_PREFIX)


def ship_current_speed(direction: Direction):
    return f"{PREFIX}:pipeline:thrust:{direction}"


def ship_current_mass_kg():
    return f"{PREFIX}:ship:current_mass_kg"


def ship_current_gravity():
    return f"{PREFIX}:ship:current_gravity"
