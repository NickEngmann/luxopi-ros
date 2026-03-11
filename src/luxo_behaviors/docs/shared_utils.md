# Shared Utilities Module

## Overview
The `shared_utils` module provides common utility functions used across collision detection, vision processing, idle behaviors, and other Luxo behaviors.

## Functions

### `calculate_distance(p1: tuple, p2: tuple) -> float`
Calculates the Euclidean distance between two 3D points.

**Parameters:**
- `p1`: First point as (x, y, z) tuple
- `p2`: Second point as (x, y, z) tuple

**Returns:** Distance in meters

**Example:**
```python
dist = calculate_distance((0, 0, 0), (1, 1, 1))  # Returns ~1.732
```

### `normalize_vector(vector: list) -> list`
Normalizes a 3D vector to unit length.

**Parameters:**
- `vector`: Input vector as [x, y, z] list

**Returns:** Normalized vector as [x, y, z] list

**Example:**
```python
normalized = normalize_vector([3, 4, 0])  # Returns [0.6, 0.8, 0.0]
```

### `clamp(value: float, min_val: float, max_val: float) -> float`
Clamps a value to be within a specified range.

**Parameters:**
- `value`: The value to clamp
- `min_val`: Minimum allowed value
- `max_val`: Maximum allowed value

**Returns:** Clamped value

**Example:**
```python
clamped = clamp(15, 0, 10)  # Returns 10.0
```

### `lerp(start: float, end: float, t: float) -> float`
Linear interpolation between two values.

**Parameters:**
- `start`: Starting value
- `end`: Ending value
- `t`: Interpolation factor (0.0 to 1.0)

**Returns:** Interpolated value

**Example:**
```python
result = lerp(0, 10, 0.5)  # Returns 5.0
```

### `angle_between(v1: list, v2: list) -> float`
Calculates the angle between two 3D vectors in radians.

**Parameters:**
- `v1`: First vector
- `v2`: Second vector

**Returns:** Angle in radians

**Example:**
```python
angle = angle_between([1, 0, 0], [0, 1, 0])  # Returns ~1.57 (90 degrees)
```

### `is_point_in_sphere(point: tuple, center: tuple, radius: float) -> bool`
Checks if a point is within a sphere.

**Parameters:**
- `point`: Point to check as (x, y, z)
- `center`: Sphere center as (x, y, z)
- `radius`: Sphere radius

**Returns:** True if point is inside sphere

**Example:**
```python
inside = is_point_in_sphere((0, 0, 0), (0, 0, 0), 5.0)  # Returns True
```

## Constants

- `DEFAULT_ARM_LENGTH = 0.3`: Default arm length in meters
- `DEFAULT_SAFE_DISTANCE = 0.2`: Default safe distance from obstacles
- `DEFAULT_VISION_RANGE = 1.0`: Default vision processing range
- `DEFAULT_SMOOTHING_FACTOR = 0.1`: Default smoothing factor for interpolation
