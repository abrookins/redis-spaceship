from collections import defaultdict
from pytest import fixture

from spaceship.models import Direction, Velocity
from spaceship.spaceship import Ship, DictDeck, DictThruster, ListEventLog

EARTH_GRAVITY = 9.8


@fixture
def ship():
    data = {
        'speed_kmh': defaultdict(float),
        'base_mass_kg': 2e6,  # 2 million kilograms
        'current_mass_kg': 2e6,
        'current_gravity': EARTH_GRAVITY,
    }
    return Ship(data,
                event_log=ListEventLog(),
                decks=[DictDeck('main', 1000)],
                aft_thruster=DictThruster('aft', data),
                forward_thruster=DictThruster('forward', data))


def test_accelerate(ship: Ship):
    ship.accelerate(Velocity(500, Direction.N))

    assert len(ship.event_log) == 6
    for event in ship.event_log.events[0:4]:
        assert event.data == {'fuel_burned': 2}
    assert ship.event_log.events[5].data == {'fuel_burned': 1.5740740740740726}

    assert round(ship.data['speed_kmh'][Direction.N]) == 500.0
