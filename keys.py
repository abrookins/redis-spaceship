import os

DEFAULT_PREFIX = "spaceship:test"

PREFIX = os.environ.get('KEY_PREFIX', DEFAULT_PREFIX)


def ion_thruster_fuel_key():
    return f"{PREFIX}:fuel:nuclear"
