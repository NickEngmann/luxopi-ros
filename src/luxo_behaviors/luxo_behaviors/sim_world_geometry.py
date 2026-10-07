"""Small ROS-free ray/obstacle helpers for the virtual sensor fixture.

Scene geometry is deliberately primitive and explicit. It is a test fixture,
not a model of a real room or calibrated robot sensor envelope.
"""

from __future__ import annotations

import math


MAX_OBSTACLES = 32
MAX_WORLD_EXTENT_M = 5.0


def _vector(values, name, *, positive=False):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError(f"{name} must contain three numbers")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must be finite")
    if any(abs(value) > MAX_WORLD_EXTENT_M for value in result):
        raise ValueError(f"{name} exceeds the {MAX_WORLD_EXTENT_M:g} m fixture bound")
    if positive and any(value <= 0.0 for value in result):
        raise ValueError(f"{name} dimensions must be positive")
    return result


def validate_obstacles(obstacles):
    """Validate a bounded list of world-frame boxes and spheres."""
    if not isinstance(obstacles, list) or len(obstacles) > MAX_OBSTACLES:
        raise ValueError(f"obstacles must be a list of at most {MAX_OBSTACLES} fixtures")
    result = []
    names = set()
    for item in obstacles:
        if not isinstance(item, dict):
            raise ValueError("each obstacle must be an object")
        name = item.get("name")
        shape = item.get("shape")
        if not isinstance(name, str) or not name or len(name) > 64 or name in names:
            raise ValueError("obstacle names must be unique non-empty strings up to 64 characters")
        names.add(name)
        center = _vector(item.get("center_m"), f"{name}.center_m")
        if shape == "box":
            dimensions = _vector(item.get("half_extents_m"), f"{name}.half_extents_m", positive=True)
        elif shape == "sphere":
            radius = float(item.get("radius_m"))
            if not math.isfinite(radius) or not 0.0 < radius <= MAX_WORLD_EXTENT_M:
                raise ValueError(f"{name}.radius_m must be finite and within the fixture bounds")
            dimensions = (radius, radius, radius)
        else:
            raise ValueError(f"{name}.shape must be 'box' or 'sphere'")
        result.append({"name": name, "shape": shape, "center_m": center, "dimensions_m": dimensions})
    return tuple(result)


def _ray_box_distance(origin, direction, center, half_extents):
    lower, upper = 0.0, math.inf
    for o, d, c, half in zip(origin, direction, center, half_extents):
        minimum, maximum = c - half, c + half
        if abs(d) <= 1e-12:
            if o < minimum or o > maximum:
                return None
            continue
        first, second = (minimum - o) / d, (maximum - o) / d
        if first > second:
            first, second = second, first
        lower, upper = max(lower, first), min(upper, second)
        if lower > upper:
            return None
    return lower if upper >= 0.0 else None


def _ray_sphere_distance(origin, direction, center, radius):
    offset = tuple(o - c for o, c in zip(origin, center))
    b = sum(o * d for o, d in zip(offset, direction))
    c = sum(o * o for o in offset) - radius * radius
    if c <= 0.0:
        # A mount already inside the fixture is an immediate obstacle, not a
        # clear ray whose first positive surface is the sphere's far side.
        return 0.0
    discriminant = b * b - c
    if discriminant < 0.0:
        return None
    first = -b - math.sqrt(discriminant)
    second = -b + math.sqrt(discriminant)
    if second < 0.0:
        return None
    return first if first >= 0.0 else second


def raycast_fixture(origin, direction, obstacles, max_range_m):
    """Return nearest ray hit distance within range, else ``None``.

    Directions are normalized here to make the return value metres regardless
    of the caller's local-frame vector scale.
    """
    origin = _vector(origin, "ray origin")
    if not isinstance(direction, (list, tuple)) or len(direction) != 3:
        raise ValueError("ray direction must contain three numbers")
    direction = tuple(float(value) for value in direction)
    if not all(math.isfinite(value) for value in direction):
        raise ValueError("ray direction must be finite")
    magnitude = math.sqrt(sum(value * value for value in direction))
    if magnitude <= 1e-12:
        raise ValueError("ray direction must be non-zero")
    direction = tuple(value / magnitude for value in direction)
    max_range = float(max_range_m)
    if not math.isfinite(max_range) or not 0.0 < max_range <= MAX_WORLD_EXTENT_M:
        raise ValueError("max_range_m is outside the fixture bounds")

    nearest = None
    for obstacle in obstacles:
        if obstacle["shape"] == "box":
            distance = _ray_box_distance(origin, direction, obstacle["center_m"], obstacle["dimensions_m"])
        else:
            distance = _ray_sphere_distance(origin, direction, obstacle["center_m"], obstacle["dimensions_m"][0])
        if distance is not None and -1e-12 <= distance <= max_range:
            nearest = distance if nearest is None else min(nearest, distance)
    return nearest


def transform_mount(body_position, body_rotation, offset_local, direction_local):
    """Transform a configured mount ray using one measured model body pose."""
    import numpy as np

    position = np.asarray(body_position, dtype=np.float64)
    rotation = np.asarray(body_rotation, dtype=np.float64)
    offset = np.asarray(offset_local, dtype=np.float64)
    direction = np.asarray(direction_local, dtype=np.float64)
    if position.shape != (3,) or rotation.shape != (3, 3) or offset.shape != (3,) or direction.shape != (3,):
        raise ValueError("mount transform requires a 3-vector, 3x3 rotation, and two 3-vectors")
    if not all(np.isfinite(values).all() for values in (position, rotation, offset, direction)):
        raise ValueError("mount transform values must be finite")
    magnitude = float(np.linalg.norm(direction))
    if magnitude <= 1e-12:
        raise ValueError("mount ray direction must be non-zero")
    return tuple(position + rotation @ offset), tuple(rotation @ (direction / magnitude))
