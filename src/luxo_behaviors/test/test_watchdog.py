#!/usr/bin/env python3
"""Tests for the watchdog node."""

import pytest
import sys
import os
import time
import threading

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 before importing watchdog components
import unittest.mock as mock

# Mock all ROS2 imports
sys.modules['rclpy'] = mock.MagicMock()
sys.modules['rclpy.node'] = mock.MagicMock()
sys.modules['rclpy.qos'] = mock.MagicMock()
sys.modules['rclpy.executors'] = mock.MagicMock()
sys.modules['std_msgs.msg'] = mock.MagicMock()
sys.modules['geometry_msgs.msg'] = mock.MagicMock()
sys.modules['diagnostic_msgs.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.srv'] = mock.MagicMock()


class TestWatchdog:
    """Tests for the Watchdog class."""
    
    def test_watchdog_creation(self):
        """Test creating a watchdog."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        assert watchdog is not None
        assert len(watchdog._monitored_components) == 0
    
    def test_add_component(self):
        """Test adding a monitored component."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 5.0,
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        
        assert len(watchdog._monitored_components) == 1
        assert watchdog._monitored_components[0]['name'] == 'test_component'
    
    def test_add_multiple_components(self):
        """Test adding multiple components."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        for i in range(3):
            component = {
                'name': f'component_{i}',
                'timeout': 5.0,
                'callback': lambda: None
            }
            watchdog.add_component(component)
        
        assert len(watchdog._monitored_components) == 3
    
    def test_remove_component(self):
        """Test removing a monitored component."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 5.0,
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        assert len(watchdog._monitored_components) == 1
        
        watchdog.remove_component('test_component')
        assert len(watchdog._monitored_components) == 0
    
    def test_update_component_heartbeat(self):
        """Test updating component heartbeat."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 5.0,
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        
        # Update heartbeat
        watchdog.update_heartbeat('test_component')
        
        # Check that heartbeat was updated
        assert 'test_component' in watchdog._last_heartbeat
    
    def test_check_component_health(self):
        """Test checking component health."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 0.1,  # Short timeout for testing
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        watchdog.update_heartbeat('test_component')
        
        # Should be healthy initially
        assert watchdog.check_health('test_component') is True
        
        # Wait for timeout
        time.sleep(0.2)
        
        # Should be unhealthy after timeout
        assert watchdog.check_health('test_component') is False
    
    def test_get_all_healthy_components(self):
        """Test getting all healthy components."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        for i in range(3):
            component = {
                'name': f'component_{i}',
                'timeout': 5.0,
                'callback': lambda: None
            }
            watchdog.add_component(component)
            watchdog.update_heartbeat(f'component_{i}')
        
        healthy = watchdog.get_healthy_components()
        assert len(healthy) == 3
    
    def test_get_unhealthy_components(self):
        """Test getting unhealthy components."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        for i in range(3):
            component = {
                'name': f'component_{i}',
                'timeout': 0.1,  # Short timeout
                'callback': lambda: None
            }
            watchdog.add_component(component)
            watchdog.update_heartbeat(f'component_{i}')
        
        # Wait for timeout
        time.sleep(0.2)
        
        unhealthy = watchdog.get_unhealthy_components()
        assert len(unhealthy) == 3
    
    def test_clear_components(self):
        """Test clearing all monitored components."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        for i in range(3):
            component = {
                'name': f'component_{i}',
                'timeout': 5.0,
                'callback': lambda: None
            }
            watchdog.add_component(component)
        
        watchdog.clear_components()
        assert len(watchdog._monitored_components) == 0
    
    def test_get_component_status(self):
        """Test getting component status."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 5.0,
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        watchdog.update_heartbeat('test_component')
        
        status = watchdog.get_component_status('test_component')
        assert status is not None
        assert status['name'] == 'test_component'
    
    def test_run_monitoring_loop(self):
        """Test running the monitoring loop."""
        from luxo_behaviors.watchdog import Watchdog
        
        watchdog = Watchdog()
        
        component = {
            'name': 'test_component',
            'timeout': 0.1,
            'callback': lambda: None
        }
        
        watchdog.add_component(component)
        watchdog.update_heartbeat('test_component')
        
        # Run monitoring for a short time
        watchdog.start_monitoring()
        time.sleep(0.3)
        watchdog.stop_monitoring()
        
        # Should have detected unhealthy component
        unhealthy = watchdog.get_unhealthy_components()
        assert len(unhealthy) == 1


class TestWatchdogNode:
    """Tests for the WatchdogNode class."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        mock.MagicMock.reset_mock()
    
    def test_node_creation(self):
        """Test creating a watchdog node."""
        from luxo_behaviors.watchdog_node import WatchdogNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = WatchdogNode()
            assert node is not None
    
    def test_handle_component_heartbeat(self):
        """Test handling component heartbeat."""
        from luxo_behaviors.watchdog_node import WatchdogNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = WatchdogNode()
            
            heartbeat_data = {
                'component_name': 'test_component',
                'timestamp': time.time()
            }
            
            result = node.handle_heartbeat(heartbeat_data)
            assert result is not None
    
    def test_generate_diagnostics(self):
        """Test generating diagnostics."""
        from luxo_behaviors.watchdog_node import WatchdogNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = WatchdogNode()
            
            diagnostics = node.generate_diagnostics()
            assert diagnostics is not None
    
    def test_handle_emergency_stop(self):
        """Test handling emergency stop."""
        from luxo_behaviors.watchdog_node import WatchdogNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = WatchdogNode()
            
            node.handle_emergency_stop()
            assert node._emergency_stop is True
    
    def test_cleanup(self):
        """Test cleanup method."""
        from luxo_behaviors.watchdog_node import WatchdogNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = WatchdogNode()
            
            # This should not raise an exception
            node.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
