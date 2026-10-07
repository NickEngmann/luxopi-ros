"""Thread-safe simulated lamp sink; records visuals without importing drivers."""
import math
import threading


class VirtualNeoPixelController:
    def __init__(self, pixel_count=60, brightness=0.5, logger=None, max_fps=15.0):
        self.pixel_count = pixel_count
        self.brightness = brightness
        self._lock = threading.RLock()
        self._revision = 0
        self._effect = 'off'
        self._color = [0, 0, 0, 0]
        self._parameters = {}

    def is_initialized(self):
        return True

    def _record(self, effect, color=(0,0,0,0), **parameters):
        normalized = list(color)
        if len(normalized) == 3:
            normalized.append(0)
        if len(normalized) != 4 or any(not math.isfinite(float(c)) for c in normalized):
            return False
        with self._lock:
            self._effect = effect
            self._color = [max(0,min(255,int(c))) for c in normalized]
            self._parameters = parameters
            self._revision += 1
        return True

    def snapshot(self):
        with self._lock:
            return dict(simulated=True, pixel_count=self.pixel_count,
                        brightness=self.brightness, rgbw=list(self._color),
                        effect=self._effect, parameters=dict(self._parameters),
                        revision=self._revision)

    def set_brightness(self, brightness):
        if not math.isfinite(float(brightness)):
            return False
        with self._lock:
            self.brightness = max(0,min(1,float(brightness)))
            self._revision += 1
        return True

    def set_solid_color(self, r, g, b, w=0):
        return self._record('solid', (r,g,b,w))

    def clear_all(self):
        return self._record('off')

    off = clear_all
    cleanup = clear_all

    def stop_effect(self):
        with self._lock:
            self._effect = 'solid'
            self._parameters = {}
            self._revision += 1

    def breathing_effect(self, color, **parameters):
        return self._record('breathing', color, **parameters)

    def spinning_dot(self, color, **parameters):
        return self._record('spinning_dot', color, **parameters)

    def spinning_group(self, color, **parameters):
        return self._record('spinning_group', color, **parameters)

    def bouncing_direction_indicator(self, primary_color, secondary_color, **parameters):
        return self._record('bouncing_direction_indicator', primary_color,
                            secondary_color=list(secondary_color), **parameters)
