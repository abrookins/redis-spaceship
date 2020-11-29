from collections import defaultdict
from spaceship import keys
from pytest import fixture
from redis import Redis

from spaceship.models import Direction, Velocity
from spaceship.spaceship import DictShip, RedisShip, DictDeck, DictThruster, ListEventLog, RedisThruster

EARTH_GRAVITY = 9.8
TWO_MILLION_KG = 2e6


@fixture
def redis():
    # TODO: Port, etc.
    r = Redis()
    yield r
    r.flushdb()



@fixture
def dict_ship():
    data = {
        'speed_kmh': defaultdict(float),
        'base_mass_kg': TWO_MILLION_KG,
        'current_mass_kg': TWO_MILLION_KG,
        'current_gravity': EARTH_GRAVITY,
    }
    return DictShip(data,
                    base_mass_kg=TWO_MILLION_KG,
                    event_log=ListEventLog(),
                    decks=[DictDeck('main', 1000)],
                    aft_thruster=DictThruster('aft', data),
                    forward_thruster=DictThruster('forward', data))


@fixture
def redis_ship(redis):
    redis.set(keys.ship_current_mass_kg(), TWO_MILLION_KG)
    redis.set(keys.ship_current_gravity(), EARTH_GRAVITY)
    return RedisShip(redis,
                     base_mass_kg=TWO_MILLION_KG,
                     event_log=ListEventLog(),
                     decks=[DictDeck('main', 1000)],
                     aft_thruster=RedisThruster('aft', redis),
                     forward_thruster=RedisThruster('forward', redis))


def test_accelerate_dict_ship(dict_ship: DictShip):
    dict_ship.accelerate(Velocity(500, Direction.N))

    assert len(dict_ship.event_log) == 6
    for event in dict_ship.event_log.events[0:4]:
        assert event.data == {'fuel_burned': 2}
    assert dict_ship.event_log.events[5].data == {
        'fuel_burned': 1.5740740740740726
    }

    assert round(dict_ship.data['speed_kmh'][Direction.N.value]) == 500.0


def test_accelerate_redis_ship(redis_ship: RedisShip):
    redis_ship.accelerate(Velocity(500, Direction.N))

    assert len(redis_ship.event_log) == 6
    for event in redis_ship.event_log.events[0:4]:
        assert event.data == {'fuel_burned': 2}
    assert redis_ship.event_log.events[5].data == {
        'fuel_burned': 1.5740740740740726
    }

    current_speed = float(redis_ship.data[keys.ship_current_speed(Direction.N)])
    assert round(current_speed) == 500.0
