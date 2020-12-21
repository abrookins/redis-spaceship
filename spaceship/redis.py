import math
from spaceship.protocols import PropulsionSystem
from redis import Redis
from spaceship.spaceship import ShipBase

from .models import Direction, Velocity, velocity_schema

from . import keys


class RedisThruster(PropulsionSystem):
    THRUST_PER_SECOND_NEWTONS = 5e7  # 50 million newtons
    FUEL_BURNED_PER_SECOND = 2  # Number of fuel units burned per second

    def __init__(self, data: Redis):
        self.data = data

    def fire(self, target_velocity: Velocity, ship_weight_kg: float, ship_mass_kg: float):
        resultant_force = self.THRUST_PER_SECOND_NEWTONS - ship_weight_kg
        acceleration_per_second_ms = resultant_force / ship_mass_kg
        acceleration_per_second_kmh = acceleration_per_second_ms * 3.6
        remainder, seconds_to_burn = math.modf(target_velocity.speed_kmh /
                                               acceleration_per_second_kmh)
        key = keys.ship_current_speed(target_velocity.direction.value)

        with self.data.pipeline(transaction=False) as p:
            # TODO: Coroutine -- yield from caller; caller decides
            # whether to continue the burn after examining fuel burned.
            for _ in range(int(seconds_to_burn)):
                self.data.incrbyfloat(key, acceleration_per_second_kmh)
                yield self.FUEL_BURNED_PER_SECOND
            p.execute()

        if remainder:
            self.data.incrbyfloat(key, acceleration_per_second_kmh * remainder)
            yield self.FUEL_BURNED_PER_SECOND * remainder


class RedisShip(ShipBase):
    def __init__(self, redis: Redis, *args, **kwargs):
        self.data = redis
        super().__init__(*args, **kwargs)
        self.data['current_velocity'] = velocity_schema.dumps(Velocity(0, Direction.N))

    @property
    def current_gravity(self):
        return float(self.data[keys.ship_current_gravity()])

    @property
    def base_weight_kg(self):
        return float(self.data[keys.ship_current_mass_kg()])
