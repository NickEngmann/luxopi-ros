"""Bounded, waypoint-preserving continuous animation trajectory prototype.

No ROS or actuator dependencies. Unlike independent eased segments, interior
waypoints need not stop every axis. Acceleration metadata is never an axis.
"""
from bisect import bisect_right
import math


class ContinuousTrajectory:
    def __init__(self, start, frames, durations, *, speed_multiplier=1.0,
                 max_velocity=.5, max_acceleration=1.0, axes=5):
        frames = tuple(tuple(map(float, frame)) for frame in frames)
        start = tuple(map(float, start))
        durations = tuple(map(float, durations))
        parameters = (speed_multiplier, max_velocity, max_acceleration)
        if any(not math.isfinite(value) or value <= 0 for value in parameters):
            raise ValueError('speed and motion limits must be finite and positive')
        if not isinstance(axes, int) or isinstance(axes, bool) or not 1 <= axes <= 5:
            raise ValueError('axes must be within 1..5')
        if not frames or len(frames) != len(durations):
            raise ValueError('nonempty frames and matching durations are required')
        if len(start) < 5 or any(len(frame) < 5 for frame in frames):
            raise ValueError('animation poses require five position fields')
        if any(not math.isfinite(value) for pose in (start, *frames) for value in pose):
            raise ValueError('poses must be finite')
        if any(not math.isfinite(value) or value <= 0 for value in durations):
            raise ValueError('durations must be finite and positive')
        self.frames, self.axes = frames, axes
        self.points = (start[:5], *(frame[:5] for frame in frames))
        times = [value / speed_multiplier for value in durations]
        # Stretch individual stages first; a short approach stage must not
        # unnecessarily slow every later stage. Tangents are recomputed because
        # neighboring durations affect their derivatives.
        for _ in range(24):
            coefficients = self._coefficients(times)
            factors = [self._scale(segment, duration, max_velocity, max_acceleration)
                       for segment, duration in zip(coefficients, times)]
            if max(factors) <= 1.0 + 1e-10:
                break
            times = [duration * max(1.0, factor * 1.000001)
                     for duration, factor in zip(times, factors)]
        # A final global scaling leaves polynomial geometry unchanged and gives
        # an analytic guarantee even if iterative local stretching did not converge.
        coefficients = self._coefficients(times)
        scale = max(self._scale(segment, duration, max_velocity, max_acceleration)
                    for segment, duration in zip(coefficients, times))
        self.durations = tuple(duration * max(1.0, scale * 1.000001) for duration in times)
        self.coefficients = self._coefficients(self.durations)
        ends, total = [], 0.0
        for duration in self.durations:
            total += duration
            ends.append(total)
        self.ends, self.total_duration = tuple(ends), total

    def _coefficients(self, times):
        slopes = [[(b[j] - a[j]) / duration for j in range(5)]
                  for a, b, duration in zip(self.points, self.points[1:], times)]
        tangents = [[0.0] * 5 for _ in self.points]
        for i in range(1, len(self.points) - 1):
            before, after = times[i-1], times[i]
            for j in range(5):
                left, right = slopes[i-1][j], slopes[i][j]
                if left * right > 0:
                    w1, w2 = 2*after + before, after + 2*before
                    tangents[i][j] = (w1+w2) / (w1/left + w2/right)
        return tuple(tuple((2*a[j]-2*b[j] + duration*(ma[j]+mb[j]),
                            -3*a[j]+3*b[j] - duration*(2*ma[j]+mb[j]),
                            duration*ma[j], a[j]) for j in range(5))
                     for a, b, ma, mb, duration in zip(
                         self.points, self.points[1:], tangents, tangents[1:], times))

    def _scale(self, segment, duration, velocity, acceleration):
        maximum = 1.0
        for a, b, c, _ in segment[:self.axes]:
            candidates = [0.0, 1.0]
            if abs(a) > 1e-15:
                vertex = -b / (3*a)
                if 0 < vertex < 1:
                    candidates.append(vertex)
            peak_velocity = max(abs(3*a*u*u + 2*b*u + c) for u in candidates) / duration
            peak_acceleration = max(abs(2*b), abs(6*a + 2*b)) / duration**2
            maximum = max(maximum, peak_velocity/velocity,
                          math.sqrt(peak_acceleration/acceleration))
        return maximum

    def segment(self, index, fraction):
        fraction = float(fraction)
        if not math.isfinite(fraction):
            raise ValueError('fraction must be finite')
        u = max(0.0, min(1.0, fraction))
        positions = [((a*u+b)*u+c)*u+d for a, b, c, d in self.coefficients[index]]
        return positions + [self.frames[index][5] if len(self.frames[index]) > 5 else 10.0]

    def sample(self, elapsed):
        elapsed = float(elapsed)
        if not math.isfinite(elapsed):
            raise ValueError('elapsed time must be finite')
        elapsed = max(0.0, min(self.total_duration, elapsed))
        index = min(len(self.ends)-1, bisect_right(self.ends, elapsed))
        beginning = self.ends[index-1] if index else 0.0
        return self.segment(index, (elapsed-beginning)/self.durations[index]), index
