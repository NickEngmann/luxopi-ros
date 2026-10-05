"""Conservative filtering for centimetre-valued VL53L4CD proximity readings."""
import math


def filtered_clearance(raw, history, *, history_size=5, outlier_threshold=15.0):
    """Never hide a closer valid observation behind older clear readings.

    Invalid data resets history and returns NaN so the classifier immediately
    marks coverage unknown. Zero is treated conservatively as imminent danger.
    ST specifies a nominal range up to 1200 mm for the VL53L4CD.
    """
    raw = float(raw)
    if not math.isfinite(raw) or not 0.0 <= raw <= 120.0:
        history.clear()
        return {'distance': float('nan'), 'valid': False, 'raw': raw}
    history.append(raw)
    del history[:-history_size]
    if len(history) < 3:
        return {'distance': raw, 'filtered': False, 'valid': True}
    ordered = sorted(history)
    median = ordered[len(ordered) // 2]
    accepted = [value for value in history if abs(value - median) <= outlier_threshold]
    smoothed = sum(accepted) / len(accepted) if accepted else median
    # Approach must be immediate; clearance may recover conservatively.
    distance = min(raw, smoothed)
    return {'distance': distance, 'filtered': distance != raw, 'raw': raw, 'valid': True}
