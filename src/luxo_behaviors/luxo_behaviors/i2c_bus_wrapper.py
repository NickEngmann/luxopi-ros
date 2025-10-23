"""
I2C Bus Wrapper for accessing software I2C buses via /dev/i2c-X devices.

This wrapper provides a busio.I2C-like interface for software I2C buses
that are created via device tree overlays (e.g., i2c-gpio).
"""

import threading
from Adafruit_PureIO.smbus import SMBus


class I2CBusWrapper:
    """
    Wrapper for I2C bus access via /dev/i2c-X device files.

    This class provides a busio.I2C-compatible interface for accessing
    I2C buses that don't have hardware support in the Blinka library.
    """

    def __init__(self, bus_num: int):
        """
        Initialize the I2C bus wrapper.

        Args:
            bus_num: The I2C bus number (e.g., 3 for /dev/i2c-3)
        """
        self._bus_num = bus_num
        self._bus = SMBus(bus_num)
        self._lock = threading.Lock()
        self._locked = False

    def try_lock(self) -> bool:
        """
        Attempt to acquire the I2C bus lock.

        Returns:
            True if the lock was acquired, False otherwise
        """
        if self._locked:
            return False
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._locked = True
        return acquired

    def unlock(self):
        """Release the I2C bus lock."""
        if self._locked:
            self._locked = False
            self._lock.release()

    def writeto(self, address: int, buffer, *, start: int = 0, end: int = None, stop: bool = True):
        """
        Write data to an I2C device.

        Args:
            address: 7-bit I2C device address
            buffer: Data to write
            start: Start index in buffer (default: 0)
            end: End index in buffer (default: len(buffer))
            stop: Whether to send I2C STOP condition (default: True)
        """
        if end is None:
            end = len(buffer)
        data = bytes(buffer[start:end])
        self._bus.write_bytes(address, data)

    def readfrom_into(self, address: int, buffer, *, start: int = 0, end: int = None, stop: bool = True):
        """
        Read data from an I2C device into a buffer.

        Args:
            address: 7-bit I2C device address
            buffer: Buffer to read data into
            start: Start index in buffer (default: 0)
            end: End index in buffer (default: len(buffer))
            stop: Whether to send I2C STOP condition (default: True)
        """
        if end is None:
            end = len(buffer)
        length = end - start
        result = self._bus.read_bytes(address, length)
        for i, byte in enumerate(result):
            buffer[start + i] = byte

    def writeto_then_readfrom(self, address: int, buffer_out, buffer_in,
                               *, out_start: int = 0, out_end: int = None,
                               in_start: int = 0, in_end: int = None, stop: bool = False):
        """
        Write data to an I2C device, then read data from it.

        Args:
            address: 7-bit I2C device address
            buffer_out: Data to write
            buffer_in: Buffer to read data into
            out_start: Start index in buffer_out (default: 0)
            out_end: End index in buffer_out (default: len(buffer_out))
            in_start: Start index in buffer_in (default: 0)
            in_end: End index in buffer_in (default: len(buffer_in))
            stop: Whether to send I2C STOP condition between write and read (default: False)
        """
        if out_end is None:
            out_end = len(buffer_out)
        if in_end is None:
            in_end = len(buffer_in)

        data_out = bytes(buffer_out[out_start:out_end])
        in_length = in_end - in_start

        # Write then read
        self._bus.write_bytes(address, data_out)
        result = self._bus.read_bytes(address, in_length)

        for i, byte in enumerate(result):
            buffer_in[in_start + i] = byte

    def scan(self):
        """
        Scan the I2C bus for devices.

        Returns:
            List of I2C addresses that responded
        """
        devices = []
        for addr in range(0x08, 0x78):
            try:
                self._bus.write_bytes(addr, [])
                devices.append(addr)
            except OSError:
                pass
        return devices

    def deinit(self):
        """Deinitialize the I2C bus."""
        if hasattr(self._bus, 'close'):
            self._bus.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.deinit()
        return False
