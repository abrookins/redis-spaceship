import os
from .models import Direction

DEFAULT_PREFIX = "spaceship:test"

PREFIX = os.environ.get('KEY_PREFIX', DEFAULT_PREFIX)


def pipeline_thruster_thrust_key(direction: Direction):
    return f"{PREFIX}:pipeline:thrust:{direction}"
