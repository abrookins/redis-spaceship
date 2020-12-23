from collections import defaultdict
from pytest import fixture
import pytest

from spaceship.errors import NoCapacityError
from spaceship.models import Direction, Person, Vehicle, Velocity
from spaceship.python import DictShip, DictDeck, DictThruster, ListEventLog

EARTH_GRAVITY = 9.8
TWO_MILLION_KG = 2e6



@fixture
def dict_ship():
    data = {
        'speed_kmh': defaultdict(float),
        'base_mass': TWO_MILLION_KG,
        'current_mass': TWO_MILLION_KG,
        'current_gravity': EARTH_GRAVITY,
        'decks': {}
    }
    return DictShip(data,
                    base_mass=TWO_MILLION_KG,
                    event_log=ListEventLog(),
                    decks=[DictDeck('main', data, 1000)],
                    thruster=DictThruster(data))


def test_accelerate_dict_ship(dict_ship: DictShip):
    dict_ship.accelerate(Velocity(500, Direction.N))

    assert len(dict_ship.event_log) == 10
    for event in dict_ship.event_log.events[0:8]:
        assert event.data == {'fuel_burned': 2}
    assert dict_ship.event_log.events[9].data == {
        'fuel_burned': 0.27485380116959135
    }

    assert round(dict_ship.data['speed_kmh'][Direction.N.value]) == 500.0


def test_load_dict_deck(dict_ship: DictShip):
    bob = Person(name="Bob", mass=86)

    assert dict_ship.weight_kg == TWO_MILLION_KG * EARTH_GRAVITY
    dict_ship.store('main', bob)
    assert dict_ship.weight_kg == (TWO_MILLION_KG + 86) * EARTH_GRAVITY


def test_load_dict_deck_over_capacity(dict_ship: DictShip):
    loader = Vehicle(name="loader mech", mass=1500)

    with pytest.raises(NoCapacityError):
        dict_ship.store('main', loader)


def test_deck_mass_affects_ship_speed(dict_ship: DictShip):
    loader = Vehicle(name="loader mech", mass=750)
    dict_ship.store('main', loader)

    dict_ship.accelerate(Velocity(500, Direction.N))

    assert len(dict_ship.event_log) == 10
    for event in dict_ship.event_log.events[0:8]:
        assert event.data == {'fuel_burned': 2}
    assert dict_ship.event_log.events[9].data == {
        'fuel_burned': 0.28612802400872894
    }

    assert round(dict_ship.data['speed_kmh'][Direction.N.value]) == 500.0

