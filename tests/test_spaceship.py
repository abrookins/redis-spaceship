from pytest import fixture

from spaceship.models import Direction, Velocity
from spaceship.spaceship import Ship, DictDeck, DictThruster, ListEventLog

EARTH_GRAVITY = 9.8


@fixture
def ship():
    return Ship(mass_kg=10000, current_gravity=EARTH_GRAVITY,
                decks=[DictDeck('main', 1000)],
                aft_thruster=DictThruster(),
                forward_thruster=DictThruster(),
                event_log=ListEventLog())


def test_accelerate(ship: Ship):
    ship.accelerate(Velocity(500, Direction.N))
    assert len(ship.event_log) == 5

    for event in ship.event_log.events:
        assert event.description == 'fuel burned: 2'
