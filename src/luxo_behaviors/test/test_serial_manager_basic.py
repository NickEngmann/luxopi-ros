import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, mock_open
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock only what's needed for basic tests
sys.modules['rclpy'] = Mock()
sys.modules['rclpy.node'] = Mock()
sys.modules['rclpy.action'] = Mock()
sys.modules['rclpy.callback_groups'] = Mock()
sys.modules['rclpy.executors'] = Mock()
sys.modules['rclpy.duration'] = Mock()
sys.modules['rclpy.time'] = Mock()
sys.modules['rclpy.constants'] = Mock()
sys.modules['std_msgs'] = Mock()
sys.modules['std_msgs.msg'] = Mock()
sys.modules['std_msgs.msg.String'] = Mock()
sys.modules['serial'] = Mock()
sys.modules['threading'] = Mock()
sys.modules['json'] = Mock()
sys.modules['time'] = Mock()
sys.modules['os'] = Mock()
sys.modules['subprocess'] = Mock()
sys.modules['atexit'] = Mock()
sys.modules['queue'] = Mock()
sys.modules['traceback'] = Mock()

class TestSerialManagerBasic:
    """Basic test cases for SerialManager class."""
    
    def test_serial_manager_init(self):
        """Test SerialManager initialization."""
        from serial_manager import SerialManager
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        
        manager = SerialManager(
            node=mock_node,
            serial_port='/dev/ttyAMA0',
            baud_rate=115200,
            read_throttle=0.0
        )
        
        assert manager.node == mock_node
        assert manager.serial_port == '/dev/ttyAMA0'
        assert manager.baud_rate == 115200
        assert manager.read_throttle == 0.0
    
    def test_serial_manager_default_values(self):
        """Test SerialManager with default values."""
        from serial_manager import SerialManager
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        
        manager = SerialManager(node=mock_node)
        
        assert manager.serial_port == '/dev/ttyAMA0'
        assert manager.baud_rate == 115200
        assert manager.read_throttle == 0.0
    
    def test_serial_manager_set_data_callback(self):
        """Test setting data callback."""
        from serial_manager import SerialManager
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        
        manager = SerialManager(node=mock_node)
        
        def dummy_callback(data):
            pass
        
        manager.set_data_callback(dummy_callback)
        assert manager.data_callback == dummy_callback
    
    def test_serial_manager_heartbeat_interval(self):
        """Test default heartbeat interval."""
        from serial_manager import SerialManager
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        
        manager = SerialManager(node=mock_node)
        
        assert manager.heartbeat_interval == 2.0
    
    def test_serial_manager_position_log_interval(self):
        """Test default position log interval."""
        from serial_manager import SerialManager
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        
        manager = SerialManager(node=mock_node)
        
        assert manager._position_log_interval == 10.0
