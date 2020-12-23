import logging
import math
from os import times
from typing import List

from redis import Redis, WatchError
from .errors import NoCapacityError
from .protocols import Deck, PropulsionSystem, ShipObject
from .spaceship import ShipBase

from . import keys
from .models import (Direction, Velocity, object_schemas_by_type,
                     velocity_schema)

log = logging.getLogger(__name__)


class InvalidItem(Exception):
    pass


class HashDeck(Deck):
    """A ship deck made with Redis Hashes."""
    def __init__(self, name: str, redis: Redis, max_storage_kg: float) -> None:
        self.name = name
        self.max_storage_kg = max_storage_kg
        self.redis = redis

    def items(self) -> List[ShipObject]:
        object_ids = self.redis.smembers(keys.deck_items_set())
        items = []

        with self.redis.pipeline(transaction=False) as p:
            for _id in object_ids:
                self.redis.get(_id)
            hashes = p.execute()

        for hash in hashes:
            schema = object_schemas_by_type.get(hash['type'])
            if not schema:
                logging.error("Unknown object in deck: hash")
            items.append(schema.load(hash))

        return items

    def store(self, obj: ShipObject):
        deck_items_key = keys.deck_items_set(self.name)
        item_key = keys.deck_item(self.name, obj.name)
        schema = object_schemas_by_type.get(obj.type)
        deck_mass_key = keys.deck_stored_mass(self.name)
        retries = 3

        with self.redis.pipeline() as p:
            while True:
                if retries == 0:
                    break
                try:
                    p.watch(deck_items_key)
                    if obj.mass > self.capacity_mass:
                        raise NoCapacityError
                    p.multi()
                    p.zadd(deck_items_key, {obj.name: obj.mass})
                    p.hset(item_key, mapping=schema.dump(obj))
                    p.incrby(deck_mass_key, obj.mass)
                    p.execute()
                    break
                except WatchError:
                    times.sleep(1)
                    retries -= 1
                    continue
                finally:
                    p.reset()

    @property
    def stored_mass(self):
        stored_mass = self.redis.get(keys.deck_stored_mass(self.name))
        return float(stored_mass) if stored_mass else 0

    @property
    def capacity_mass(self) -> float:
        """The current capacity of this deck."""
        return self.max_storage_kg - self.stored_mass

    def get(self, item_name) -> ShipObject:
        item_key = keys.deck_item(self.name, item_name)
        hash = self.redis.hgetall(item_key)
        schema = object_schemas_by_type.get(hash['type'])

        if not schema:
            raise InvalidItem(item_name)

        return schema.load(hash)


class PipelineThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, redis: Redis):
        self.redis = redis

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass: float):
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass
        acceleration_per_second_kmh = acceleration_per_second_ms * 3.6
        remainder, seconds_to_burn = math.modf(target_velocity.speed_kmh /
                                               acceleration_per_second_kmh)
        key = keys.ship_current_speed(target_velocity.direction.value)

        with self.redis.pipeline(transaction=False) as p:
            # TODO: Coroutine -- yield from caller; caller decides
            # whether to continue the burn after examining fuel burned?
            for _ in range(int(seconds_to_burn)):
                self.redis.incrbyfloat(key, acceleration_per_second_kmh)
                yield self.FUEL_BURNED_PER_SECOND
            p.execute()

        if remainder:
            self.redis.incrbyfloat(key, acceleration_per_second_kmh * remainder)
            yield self.FUEL_BURNED_PER_SECOND * remainder


class RedisShip(ShipBase):
    def __init__(self, redis: Redis, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = redis
        self.redis['current_velocity'] = velocity_schema.dumps(Velocity(0, Direction.N))

    @property
    def current_gravity(self):
        return float(self.redis.get(keys.ship_current_gravity()))

    @property
    def base_weight_kg(self):
        return float(self.redis.get(keys.ship_current_mass()))

    @property
    def mass(self):
        return self.base_mass + sum(deck.stored_mass for deck in
                                       self.decks.values())
