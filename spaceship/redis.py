import logging
import math
from os import times
from typing import List, Union

from redis import Redis, WatchError
from .errors import NoCapacityError
from .protocols import Deck, EventLog, PropulsionSystem, ShipObject, Ship, ShipObjectContainer

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

    def store(self, obj: Union[ShipObject, ShipObjectContainer]):
        deck_items_key = keys.deck_items_set(self.name)
        item_key = keys.deck_item(self.name, obj.name)
        schema = object_schemas_by_type.get(obj.type)
        deck_mass_key = keys.deck_stored_mass(self.name)
        objects = []
        retries = 3

        if hasattr(obj, 'objects'):
            # This is a container, so we need to be persist its objects.
            objects = obj.objects

        with self.redis.pipeline() as p:
            while True:
                if retries == 0:
                    break
                try:
                    p.watch(deck_items_key)
                    # The mass of a vehicle includes any objects it carries, so
                    # we don't need to check the mass of individual objects in
                    # a container.
                    if obj.mass > self.capacity_mass:
                        raise NoCapacityError
                    p.multi()

                    object_dict = schema.dump(obj)
                    # Redis can't store lists in a hash, so we persist objects
                    # within a container object separately.
                    object_dict.pop('objects', None)

                    # Persist objects in a container in their own hashes -- and
                    # link them to the container using a sorted set.
                    for contained_obj in objects:
                        item_schema = object_schemas_by_type[contained_obj.type]
                        container_key = keys.container_items_set(obj.name)
                        container_item_key = keys.container_item(obj.name, contained_obj.name)
                        p.zadd(container_key, {contained_obj.name: contained_obj.mass})
                        p.hset(container_item_key, mapping=item_schema.dump(contained_obj))

                    p.zadd(deck_items_key, {obj.name: obj.mass})
                    p.hset(item_key, mapping=object_dict)
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

    def load_object(self, redis_hash):
        schema = object_schemas_by_type.get(redis_hash['type'])
        item_name = redis_hash.get('name') or 'Unknown'

        if not schema:
            raise InvalidItem(item_name)

        obj = schema.load(redis_hash)
        return obj

    def get(self, name) -> ShipObject:
        item_key = keys.deck_item(self.name, name)
        redis_hash = self.redis.hgetall(item_key)
        obj = self.load_object(redis_hash)

        if obj.type != 'vehicle':
            return obj

        # If this is a container type, we need to find all of its
        # objects and load them.
        container_key = keys.container_items_set(obj.name)
        container_object_names = self.redis.zrange(container_key, 0, -1)
        with self.redis.pipeline(transaction=False) as p:
            for _name in container_object_names:
                container_item_key = keys.container_item(obj.name, _name)
                p.hgetall(container_item_key)
            hashes = p.execute()

        for _hash in hashes:
            container_obj = self.load_object(_hash)
            obj.objects.append(container_obj)

        return obj

class PipelineThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, redis: Redis):
        self.redis = redis

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass: float):
        # TODO: Separate reusable math?
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass
        acceleration_per_second_kmh = acceleration_per_second_ms * 3.6
        remainder, seconds_to_burn = math.modf(target_velocity.speed_kmh /
                                               acceleration_per_second_kmh)
        key = keys.ship_current_speed(target_velocity.direction.value)
        target_burn = int(seconds_to_burn)

        with self.redis.pipeline(transaction=False) as p:
            for i in range(target_burn):
                self.redis.incrbyfloat(key, acceleration_per_second_kmh)
                next_burn = self.FUEL_BURNED_PER_SECOND if i < target_burn else remainder
                yield self.FUEL_BURNED_PER_SECOND, next_burn
            p.execute()

        if remainder:
            self.redis.incrbyfloat(key, acceleration_per_second_kmh * remainder)
            yield self.FUEL_BURNED_PER_SECOND * remainder, 0


class RedisShip(Ship):
    def __init__(self, redis: Redis, event_log: EventLog, base_mass: float, thruster: PropulsionSystem,
                 decks: List[Deck], low_fuel_threshold: float = 0) -> None:
        self.base_mass = base_mass
        self.thruster = thruster
        self.decks = {deck.name: deck for deck in decks}
        self.event_log = event_log
        self.redis = redis
        self.redis['current_velocity'] = velocity_schema.dumps(Velocity(0, Direction.N))
        self.low_fuel_threshold = low_fuel_threshold

    @property
    def fuel(self):
        return float(self.redis.get(keys.ship_current_fuel()))

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
