import pytest
from spaceship import keys
from pytest import fixture
from redis import Redis

from spaceship.models import Direction, Person, Vehicle, Velocity
from spaceship.errors import NoCapacityError
from spaceship.python import ListEventLog
from spaceship.redis import HashDeck, RedisShip, PipelineThruster


EARTH_GRAVITY = 9.8
TWO_MILLION_KG = 2e6



@fixture
def redis():
    # TODO: Port, etc.
    r = Redis(decode_responses=True)
    yield r
    r.flushdb()


@fixture
def redis_ship(redis):
    redis.set(keys.ship_current_mass(), TWO_MILLION_KG)
    redis.set(keys.ship_current_gravity(), EARTH_GRAVITY)
    return RedisShip(redis,
                     base_mass=TWO_MILLION_KG,
                     event_log=ListEventLog(),
                     decks=[HashDeck('main', redis, 1000)],
                     thruster=PipelineThruster(redis))



def test_accelerate_redis_ship(redis_ship: RedisShip):
    redis_ship.accelerate(Velocity(500, Direction.N))

    assert len(redis_ship.event_log) == 10
    for event in redis_ship.event_log.events[0:8]:
        assert event.data == {'fuel_burned': 2}
    assert redis_ship.event_log.events[9].data == {
        'fuel_burned': 0.27485380116959135
    }

    current_speed = float(redis_ship.redis.get(keys.ship_current_speed(Direction.N.value)))
    assert round(current_speed) == 500.0


def test_redis_deck_store(redis_ship: RedisShip):
    bob = Person(name="Bob", mass=86)

    assert redis_ship.weight_kg == TWO_MILLION_KG * EARTH_GRAVITY
    redis_ship.store('main', bob)
    assert redis_ship.weight_kg == (TWO_MILLION_KG + 86) * EARTH_GRAVITY

    assert redis_ship.decks['main'].get("Bob") == bob


def test_redis_deck_capacity_mass(redis_ship: RedisShip):
    bob = Person(name="Bob", mass=86)
    redis_ship.decks['main'].store(bob)
    assert redis_ship.decks['main'].capacity_mass== 914


def test_redis_deck_over_capacity(redis):
    deck = HashDeck('main', redis, 1000)
    loader = Vehicle(name="loader mech", mass=1500)

    with pytest.raises(NoCapacityError):
        deck.store(loader)


def test_deck_mass_affects_ship_speed(redis_ship: RedisShip):
    loader = Vehicle(name="loader mech", mass=750)
    redis_ship.store('main', loader)

    redis_ship.accelerate(Velocity(500, Direction.N))

    assert len(redis_ship.event_log) == 10
    for event in redis_ship.event_log.events[0:8]:
        assert event.data == {'fuel_burned': 2}
    assert redis_ship.event_log.events[9].data == {
        'fuel_burned': 0.28612802400872894
    }

    current_speed = float(redis_ship.redis.get(keys.ship_current_speed(Direction.N.value)))
    assert round(current_speed) == 500.0

