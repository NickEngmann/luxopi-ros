#!/usr/bin/env python3
"""Tests for serial control functionality."""

import pytest
import sys
import os
import time
import threading

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock serial and ROS2 before importing serial control components
import unittest.mock as mock

# Mock serial
mock_serial = mock.MagicMock()
sys.modules['serial'] = mock_serial
sys.modules['serial.tools'] = mock.MagicMock()
sys.modules['serial.tools.list_ports'] = mock.MagicMock()

# Mock ROS2 imports
sys.modules['rclpy'] = mock.MagicMock()
sys.modules['rclpy.node'] = mock.MagicMock()
sys.modules['rclpy.qos'] = mock.MagicMock()
sys.modules['rclpy.executors'] = mock.MagicMock()
sys.modules['std_msgs.msg'] = mock.MagicMock()
sys.modules['geometry_msgs.msg'] = mock.MagicMock()
sys.modules['diagnostic_msgs.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.srv'] = mock.MagicMock()


class TestSerialController:
    """Tests for the SerialController class."""
    
    def test_controller_creation(self):
        """Test creating a serial controller."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        assert controller is not None
        assert controller._serial_port is None
    
    def test_open_port(self):
        """Test opening a serial port."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock the serial port
        mock_port = mock.MagicMock()
        mock_serial.Serial.return_value = mock_port
        
        result = controller.open_port('/dev/ttyUSB0', 115200)
        assert result is True
        assert controller._serial_port is not None
    
    def test_open_port_invalid(self):
        """Test opening an invalid serial port."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Make serial.open raise an exception
        mock_serial.Serial.side_effect = Exception("Port not found")
        
        result = controller.open_port('/dev/invalid', 115200)
        assert result is False
    
    def test_close_port(self):
        """Test closing a serial port."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Open a port first
        mock_port = mock.MagicMock()
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Close the port
        controller.close_port()
        
        assert controller._serial_port is None
        mock_port.close.assert_called_once()
    
    def test_send_command(self):
        """Test sending a command."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock the serial port
        mock_port = mock.MagicMock()
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Send a command
        command = 'MOVE 90 45 30'
        result = controller.send_command(command)
        
        assert result is True
        mock_port.write.assert_called_once()
    
    def test_send_command_no_port(self):
        """Test sending command without open port."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Don't open a port
        command = 'MOVE 90 45 30'
        result = controller.send_command(command)
        
        assert result is False
    
    def test_receive_response(self):
        """Test receiving a response."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock the serial port with response data
        mock_port = mock.MagicMock()
        mock_port.readline.return_value = b'OK\n'
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Receive response
        response = controller.receive_response(timeout=1.0)
        
        assert response is not None
        assert b'OK' in response
    
    def test_receive_response_timeout(self):
        """Test receiving response with timeout."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock the serial port with no data
        mock_port = mock.MagicMock()
        mock_port.readline.return_value = b''
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Try to receive with short timeout
        response = controller.receive_response(timeout=0.01)
        
        assert response is None
    
    def test_parse_response(self):
        """Test parsing response data."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Test various response formats
        responses = [
            b'OK\n',
            b'ERROR: Invalid command\n',
            b'POS: 90 45 30\n',
            b'STATUS: IDLE\n'
        ]
        
        for response in responses:
            parsed = controller.parse_response(response)
            assert parsed is not None
    
    def test_get_available_ports(self):
        """Test getting available serial ports."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock list_ports
        mock_ports = [
            mock.MagicMock(device='/dev/ttyUSB0'),
            mock.MagicMock(device='/dev/ttyUSB1'),
            mock.MagicMock(device='/dev/ttyACM0')
        ]
        mock_serial.tools.list_ports.comports.return_value = mock_ports
        
        ports = controller.get_available_ports()
        
        assert len(ports) == 3
        assert '/dev/ttyUSB0' in ports
    
    def test_send_and_receive(self):
        """Test sending command and receiving response."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Mock the serial port
        mock_port = mock.MagicMock()
        mock_port.readline.return_value = b'OK\n'
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Send and receive
        command = 'MOVE 90 45 30'
        response = controller.send_and_receive(command, timeout=1.0)
        
        assert response is not None
        assert b'OK' in response
    
    def test_cleanup(self):
        """Test cleanup method."""
        from luxo_behaviors.serial_ctrl import SerialController
        
        controller = SerialController()
        
        # Open a port first
        mock_port = mock.MagicMock()
        mock_serial.Serial.return_value = mock_port
        controller.open_port('/dev/ttyUSB0', 115200)
        
        # Cleanup
        controller.cleanup()
        
        mock_port.close.assert_called_once()


class TestSerialControllerNode:
    """Tests for the SerialControllerNode class."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        mock.MagicMock.reset_mock()
    
    def test_node_creation(self):
        """Test creating a serial controller node."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            assert node is not None
    
    def test_handle_move_command(self):
        """Test handling move commands."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            
            # Mock the serial controller
            mock_serial_ctrl = mock.MagicMock()
            mock_serial_ctrl.send_command.return_value = True
            node._serial_ctrl = mock_serial_ctrl
            
            # Handle move command
            result = node.handle_move_command(90, 45, 30)
            assert result is True
    
    def test_handle_joint_command(self):
        """Test handling joint commands."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            
            # Mock the serial controller
            mock_serial_ctrl = mock.MagicMock()
            mock_serial_ctrl.send_command.return_value = True
            node._serial_ctrl = mock_serial_ctrl
            
            # Handle joint command
            joints = [0.5, 0.3, 0.2, 0.1, 0.4, 0.6]
            result = node.handle_joint_command(joints)
            assert result is True
    
    def test_handle_gripper_command(self):
        """Test handling gripper commands."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            
            # Mock the serial controller
            mock_serial_ctrl = mock.MagicMock()
            mock_serial_ctrl.send_command.return_value = True
            node._serial_ctrl = mock_serial_ctrl
            
            # Handle gripper command
            result = node.handle_gripper_command(50)  # 50% grip
            assert result is True
    
    def test_handle_emergency_stop(self):
        """Test handling emergency stop."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            
            node.handle_emergency_stop()
            assert node._emergency_stop is True
    
    def test_cleanup(self):
        """Test cleanup method."""
        from luxo_behaviors.serial_ctrl_node import SerialControllerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = SerialControllerNode()
            
            # This should not raise an exception
            node.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
