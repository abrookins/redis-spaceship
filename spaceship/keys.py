import os
from .models import Direction

DEFAULT_PREFIX = "spaceship:test"

PREFIX = os.environ.get('KEY_PREFIX', DEFAULT_PREFIX)


def ship_current_speed(direction: Direction):
    return f"{PREFIX}:pipeline:thrust:{direction}"


def ship_current_mass():
    return f"{PREFIX}:ship:current_mass"


def ship_current_gravity():
    return f"{PREFIX}:ship:current_gravity"


def deck_stored_mass(deck_name: str):
    return f"{PREFIX}:deck:{deck_name}:stored_mass"


def deck_items_set(deck_name:str):
    return f"{PREFIX}:deck:{deck_name}:items"


def deck_item(deck_name: str, item_name: str):
    return f"{PREFIX}:{deck_name}:{item_name}"
