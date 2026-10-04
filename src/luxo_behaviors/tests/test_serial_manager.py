"""Unit tests for serialized serial-port writes without robot hardware."""

import sys
import threading
import types
import unittest
from queue import Queue
from unittest.mock import patch
from unittest.mock import MagicMock


# SerialManager's runtime dependencies are not needed for this port-level fake.
sys.modules.setdefault("serial", types.SimpleNamespace(SerialException=Exception))
std_msgs = sys.modules.setdefault("std_msgs", types.ModuleType("std_msgs"))
std_msgs_msg = sys.modules.setdefault("std_msgs.msg", types.ModuleType("std_msgs.msg"))
std_msgs_msg.String = type("String", (), {})
std_msgs.msg = std_msgs_msg

from luxo_behaviors.serial_manager import SerialManager  # noqa: E402
from luxo_behaviors.serial_manager import _STOP_WRITER  # noqa: E402


class FakeSerial:
    """Capture writes and prove that one thread owns all port writes."""

    def __init__(self):
        self.is_open = True
        self.writes = []
        self.writer_threads = []

    def write(self, payload):
        self.writes.append(payload)
        self.writer_threads.append(threading.get_ident())

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False


class TestSerialWriter(unittest.TestCase):
    def make_manager(self):
        manager = SerialManager.__new__(SerialManager)
        manager.node = MagicMock()
        manager.node.get_clock.return_value.now.return_value = "test-time"
        manager._state_lock = threading.RLock()
        manager._connection_active = True
        manager._running = True
        manager._read_thread_active = False
        manager._read_thread = None
        manager._write_queue = Queue(maxsize=100)
        manager._write_timeout = 1.0
        manager._last_feedback_poll_time = "before-poll"
        manager.feedback_poll_interval = 2.0
        manager._ser = FakeSerial()
        manager._write_thread = threading.Thread(target=manager._write_loop, daemon=True)
        manager._write_thread.start()
        return manager

    def test_commands_and_feedback_polls_share_one_ordered_writer(self):
        manager = self.make_manager()
        self.addCleanup(manager.close)

        self.assertTrue(manager.send_command('{"T": 101}'))
        manager._poll_position_feedback()
        self.assertTrue(manager.send_command('{"T": 102}\n'))

        self.assertEqual(
            manager._ser.writes,
            [b'{"T": 101}\r\n', b'{"T": 105}\r\n', b'{"T": 102}\r\n'],
        )
        self.assertEqual(len(set(manager._ser.writer_threads)), 1)
        self.assertEqual(manager._last_feedback_poll_time, "test-time")

    def test_connect_uses_feedback_query_instead_of_emergency_stop(self):
        manager = SerialManager.__new__(SerialManager)
        manager.node = MagicMock()
        manager.node.get_clock.return_value.now.return_value = "test-time"
        manager.serial_port = "/dev/fake"
        manager.baud_rate = 115200
        manager._state_lock = threading.RLock()
        manager._connection_active = False
        manager._running = False
        manager._read_thread = None
        manager.close = MagicMock()
        manager.check_fix_permissions = MagicMock(return_value=True)
        manager.send_command = MagicMock(return_value=True)
        fake_port = MagicMock(is_open=True)
        fake_serial_module = types.SimpleNamespace(Serial=MagicMock(return_value=fake_port))

        with patch("luxo_behaviors.serial_manager.serial", fake_serial_module), \
                patch("luxo_behaviors.serial_manager.time.sleep"), \
                patch("luxo_behaviors.serial_manager.threading.Thread") as thread_factory:
            thread_factory.return_value.start = MagicMock()
            self.assertTrue(manager.connect())

        sent_command = manager.send_command.call_args.args[0]
        self.assertEqual(sent_command, '{"T": 105}')
        self.assertNotEqual(sent_command, '{"T": 0}')

    def test_write_error_marks_connection_inactive_and_returns_false(self):
        manager = self.make_manager()
        self.addCleanup(manager.close)

        def fail_write(_payload):
            raise OSError("simulated disconnected port")

        manager._ser.write = fail_write
        self.assertFalse(manager.send_command('{"T": 104}'))
        self.assertFalse(manager.is_connected())

    def test_close_stops_writer_and_rejects_later_commands(self):
        manager = self.make_manager()
        manager.close()

        self.assertFalse(manager._write_thread)
        self.assertFalse(manager.send_command('{"T": 101}'))
        self.assertFalse(manager._ser)


if __name__ == "__main__":
    unittest.main()
